"""
Image -> OCR data (Gemini) with local cache and confidence.
Uses google-genai (new SDK).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _heuristic_confidence(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    t = text.strip()
    score = 0.5
    if len(t) >= 2:
        score += 0.2
    if any(c.isdigit() for c in t):
        score += 0.1
    if any(c in t for c in "→←↑↓·•-"):
        score += 0.1
    return min(1.0, score)


def _image_to_structured_ocr_impl(
    image_path: Path,
    *,
    api_key: str,
    model_name: str = "gemini-2.5-flash",
    language_hint: str = "中英文",
    request_confidence: bool = True,
) -> list[dict[str, Any]]:
    from google import genai
    from google.genai import types

    path = Path(image_path)
    data = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

    client = genai.Client(api_key=api_key)

    confidence_instruction = '\n对每一项增加字段 "confidence"，表示该行识别的置信度：0.0~1.0 或 "high"/"medium"/"low"。' if request_confidence else ""

    prompt = f"""这是一页手写笔记的图片。请识别图中所有手写文字（可能包含{language_hint}），按**行**输出为 JSON 数组，且尽量保持与图中一致的**上下顺序**。
每项格式：{{ "text": "该行原文", "y_ratio": 0.0~1.0, "x_ratio": 0.0~1.0 }}。y_ratio 表示该行在整页中的垂直相对位置（0=页顶，1=页底），x_ratio 表示水平相对位置（0=页左，1=页右）。
若能从图中看出**行与行之间的关系**（如箭头指向、流程顺序、上下级、并列），请为该项增加 "links" 字段，值为**行号数组**（从 0 开始，表示该行指向或连接到的其他行的下标）。例如第 0 行指向第 1、2 行则 "links": [1, 2]。没有明确关系可省略 links。
若某行文字被**框住**或**圈住**，请增加 "shape" 字段，值为 "box"（矩形框）或 "circle"（椭圆/圆）；没有框圈则省略。
若图中某行使用了**不同颜色**（如红、蓝、绿），请增加 "color" 字段，值为 CSS 颜色名或十六进制（如 "red"、"#c00"）；默认黑色可省略。
只输出一个 JSON 数组，不要其他说明。{confidence_instruction}

示例：[{{ "text": "需求", "y_ratio": 0.15, "x_ratio": 0.2, "links": [1, 2], "shape": "box" }}, {{ "text": "实现", "y_ratio": 0.3, "x_ratio": 0.2, "color": "blue" }}, ...]
"""
    contents = [
        types.Part.from_bytes(data=data, mime_type=mime),
        types.Part.from_text(text=prompt),
    ]
    response = client.models.generate_content(
        model=model_name,
        contents=contents,
    )
    try:
        raw = response.text if response else ""
    except Exception as e:
        raise RuntimeError(f"Gemini did not return text: {e}") from e
    raw = raw.strip()
    m = re.search(r"\[[\s\S]*\]", raw)
    if not m:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        n = max(len(lines), 1)
        return [{"text": ln, "y_ratio": (i + 0.5) / n, "x_ratio": 0.5} for i, ln in enumerate(lines)]
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        n = max(len(lines), 1)
        return [{"text": ln, "y_ratio": (i + 0.5) / n, "x_ratio": 0.5} for i, ln in enumerate(lines)]
    out = []
    for i, item in enumerate(arr):
        if not isinstance(item, dict):
            continue
        text = item.get("text") or ""
        y = item.get("y_ratio")
        y = (i + 0.5) / max(len(arr), 1) if y is None or not isinstance(y, (int, float)) else max(0.0, min(1.0, float(y)))
        x = item.get("x_ratio")
        x = 0.5 if x is None or not isinstance(x, (int, float)) else max(0.0, min(1.0, float(x)))
        row = {"text": text, "y_ratio": y, "x_ratio": x}
        if "confidence" in item and item["confidence"] is not None:
            c = item["confidence"]
            if isinstance(c, (int, float)):
                row["confidence"] = max(0.0, min(1.0, float(c)))
            elif isinstance(c, str) and c.lower() in ("high", "medium", "low"):
                row["confidence"] = c.lower()
            else:
                row["confidence"] = c
        if "links" in item and isinstance(item["links"], list):
            row["links"] = [int(n) for n in item["links"] if isinstance(n, (int, float)) and 0 <= int(n) < len(arr)]
        if "shape" in item and item.get("shape") in ("box", "circle"):
            row["shape"] = item.get("shape")
        if "color" in item and item.get("color"):
            row["color"] = str(item.get("color")).strip()
        out.append(row)
    out.sort(key=lambda r: (r["y_ratio"], r["x_ratio"]))
    return out


def ocr_image(
    image_path: Path | str,
    cache_dir: Path,
    *,
    cache_key: str | None = None,
    return_confidence: bool = True,
    api_key: str | None = None,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """
    Run OCR on a single note image; write result to cache_dir. If cache exists and use_cache,
    return from cache. cache_key used as cache filename (e.g. page_0 -> page_0.json).
    Returns list of rows: { "text", "y_ratio", "x_ratio", "confidence"? , "links"? , "shape"? , "color"? }.
    """
    from ..config import get_ocr_api_key, load_env

    load_env()
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")

    key = cache_key if cache_key is not None else hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"

    # Use cache when present and not skipping (we do not compare mtime to page image)
    if use_cache and cache_file.is_file():
        raw = cache_file.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                out = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    row = {
                        "text": item.get("text", ""),
                        "y_ratio": max(0.0, min(1.0, float(item.get("y_ratio", 0.5)))),
                        "x_ratio": max(0.0, min(1.0, float(item.get("x_ratio", 0.5)))),
                    }
                    if "confidence" in item:
                        row["confidence"] = item["confidence"]
                    if "links" in item and isinstance(item.get("links"), list):
                        row["links"] = [int(n) for n in item["links"] if isinstance(n, (int, float))]
                    if "shape" in item and item.get("shape") in ("box", "circle"):
                        row["shape"] = item.get("shape")
                    if "color" in item and item.get("color"):
                        row["color"] = str(item.get("color")).strip()
                    out.append(row)
                out.sort(key=lambda r: (r["y_ratio"], r["x_ratio"]))
                logger.info("OCR %s: using local cache (no Gemini request)", key)
                return out
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # No valid cache: call Gemini (first run or --no-cache)
    if use_cache and not cache_file.is_file():
        logger.info("OCR %s: no local cache, calling Gemini API", key)
    elif not use_cache:
        logger.info("OCR %s: --no-cache, calling Gemini API", key)

    api_key = api_key or get_ocr_api_key()
    if not api_key:
        raise ValueError("Set GOOGLE_API_KEY or pass api_key")

    result = _image_to_structured_ocr_impl(path, api_key=api_key, request_confidence=return_confidence)
    if return_confidence:
        for row in result:
            if "confidence" not in row:
                row["confidence"] = _heuristic_confidence(row.get("text", ""))

    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
