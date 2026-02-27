"""
Image -> OCR data using OpenAI SDK (supports OpenAI, DeepSeek, etc.)
with local cache and confidence.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from ..config import get_ocr_api_key, get_ocr_base_url, get_ocr_model_name, load_env

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

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


def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def _image_to_structured_ocr_impl(
    image_path: Path,
    *,
    api_key: str,
    base_url: str | None = None,
    model_name: str | None = None,
    language_hint: str = "Chinese and English",
    request_confidence: bool = True,
) -> list[dict[str, Any]]:
    if OpenAI is None:
        raise ImportError("Please install openai: pip install openai")

    client = OpenAI(api_key=api_key, base_url=base_url)

    model = model_name or get_ocr_model_name()
    
    base64_image = _encode_image(image_path)
    mime_type = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    
    confidence_instruction = '\nAdd a "confidence" field to each item: 0.0–1.0 or "high"/"medium"/"low".' if request_confidence else ""

    prompt = f"""This is an image of a handwritten note. Recognize all handwritten text (may include {language_hint}) and output a JSON array by **line**, preserving the **vertical order** as in the image.
Each item: {{ "text": "the line content", "y_ratio": 0.0–1.0, "x_ratio": 0.0–1.0 }}. y_ratio = vertical position (0=top, 1=bottom), x_ratio = horizontal position (0=left, 1=right).
If you can see **relationships between lines** (arrows, flow, hierarchy, list), add "links" as an array of **zero-based line indices** this line points to (e.g. line 0 points to 1 and 2 → "links": [1, 2]). Omit if no clear relationship.
If a line is **inside a box or circle**, add "shape": "box" (rectangle) or "circle" (ellipse/circle). Omit otherwise.
If a line uses a **different color** (e.g. red, blue, green), add "color" as a CSS color name or hex (e.g. "red", "#c00"). Omit for default black.
Output only one JSON array, no other text.{confidence_instruction}

Example: [{{ "text": "Requirement", "y_ratio": 0.15, "x_ratio": 0.2, "links": [1, 2], "shape": "box" }}, {{ "text": "Implementation", "y_ratio": 0.3, "x_ratio": 0.2, "color": "blue" }}, ...]
"""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64_image}"
                    },
                },
            ],
        }
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"OpenAI SDK request failed: {e}") from e

    raw = content.strip() if content else ""
    
    # Extract JSON array from markdown code block if present
    m = re.search(r"```json\s*(\[[\s\S]*\])\s*```", raw)
    if m:
        raw = m.group(1)
    else:
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            raw = m.group(0)

    try:
        arr = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: treat as plain text lines
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
                logger.info("OCR %s: using local cache (no API request)", key)
                return out
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # No valid cache: call API (first run or --no-cache)
    if use_cache and not cache_file.is_file():
        logger.info("OCR %s: no local cache, calling API", key)
    elif not use_cache:
        logger.info("OCR %s: --no-cache, calling API", key)

    api_key = api_key or get_ocr_api_key()
    if not api_key:
        raise ValueError("Set OCR_API_KEY (or OPENAI_API_KEY) or pass api_key")

    result = _image_to_structured_ocr_impl(
        path,
        api_key=api_key,
        base_url=get_ocr_base_url(),
        request_confidence=return_confidence
    )
    
    if return_confidence:
        for row in result:
            if "confidence" not in row:
                row["confidence"] = _heuristic_confidence(row.get("text", ""))

    cache_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
