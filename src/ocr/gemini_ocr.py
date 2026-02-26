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
    language_hint: str = "Chinese and English",
    request_confidence: bool = True,
) -> list[dict[str, Any]]:
    from google import genai
    from google.genai import types

    path = Path(image_path)
    data = path.read_bytes()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"

    client = genai.Client(api_key=api_key)

    confidence_instruction = '\nAdd a "confidence" field to each item: 0.0–1.0 or "high"/"medium"/"low".' if request_confidence else ""

    prompt = f"""This is an image of a handwritten note. Recognize all handwritten text (may include {language_hint}) and output a JSON array by **line**, preserving the **vertical order** as in the image.
Each item: {{ "text": "the line content", "y_ratio": 0.0–1.0, "x_ratio": 0.0–1.0 }}. y_ratio = vertical position (0=top, 1=bottom), x_ratio = horizontal position (0=left, 1=right).
If you can see **relationships between lines** (arrows, flow, hierarchy, list), add "links" as an array of **zero-based line indices** this line points to (e.g. line 0 points to 1 and 2 → "links": [1, 2]). Omit if no clear relationship.
If a line is **inside a box or circle**, add "shape": "box" (rectangle) or "circle" (ellipse/circle). Omit otherwise.
If a line uses a **different color** (e.g. red, blue, green), add "color" as a CSS color name or hex (e.g. "red", "#c00"). Omit for default black.
Output only one JSON array, no other text.{confidence_instruction}

Example: [{{ "text": "Requirement", "y_ratio": 0.15, "x_ratio": 0.2, "links": [1, 2], "shape": "box" }}, {{ "text": "Implementation", "y_ratio": 0.3, "x_ratio": 0.2, "color": "blue" }}, ...]
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
