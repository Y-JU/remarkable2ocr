"""
Parse OCR lines into content-agnostic chart semantic JSON (ChartSchema) for the renderer.
Uses OpenAI SDK.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path
from typing import Any

from .chart_schema import CHART_SCHEMA_INSTRUCTION
from ..config import get_ocr_api_key, get_ocr_base_url, get_ocr_model_name, load_env

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger(__name__)


def _encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def semantic_parse(
    ocr_lines: list[dict[str, Any]],
    image_path: Path | str | None = None,
    *,
    api_key: str | None = None,
    model_name: str | None = None,
) -> dict[str, Any]:
    """
    Call LLM with OCR lines (+ optional image) and return ChartSchema JSON.
    """
    load_env()
    key = api_key or get_ocr_api_key()
    if not key:
        raise ValueError("Set OCR_API_KEY (or OPENAI_API_KEY) or pass api_key")
        
    if OpenAI is None:
        raise ImportError("Please install openai: pip install openai")
        
    client = OpenAI(api_key=key, base_url=get_ocr_base_url())
    model = model_name or get_ocr_model_name()

    lines_text = []
    for i, row in enumerate(ocr_lines):
        t = row.get("text", "").strip()
        y = row.get("y_ratio", 0.5)
        x = row.get("x_ratio", 0.5)
        lines_text.append(f"[{i}] y={y:.2f} x={x:.2f} | {t}")
    ocr_block = "\n".join(lines_text)

    prompt = f"""Below is the OCR result of one page of handwritten notes. Each line format: [line index] y=vertical ratio x=horizontal ratio | recognized text.
Infer **structure** from **position and text** of these lines: outline hierarchy, boxes (rectangle/ellipse/longbar), arrow connections, list types, etc.
{CHART_SCHEMA_INSTRUCTION}

OCR lines (sorted by y):
{ocr_block}
"""

    messages = []
    content_parts = [{"type": "text", "text": prompt}]
    
    if image_path:
        p = Path(image_path)
        if p.is_file():
            b64 = _encode_image(p)
            mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{b64}"
                }
            })
            
    messages.append({"role": "user", "content": content_parts})

    logger.info("Semantic parse: calling API (chart structure)")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"LLM did not return text: {e}") from e

    raw = content.strip() if content else ""

    # Extract JSON from markdown if present
    m = re.search(r"```json\s*(\{[\s\S]*\})\s*```", raw)
    if m:
        raw = m.group(1)
    else:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            raw = m.group(0)
    
    if not raw:
        return {"outline": [], "containers": [], "arrows": [], "lists": []}

    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {"outline": [], "containers": [], "arrows": [], "lists": []}

    return {
        "outline": obj.get("outline", []),
        "containers": obj.get("containers", []),
        "arrows": obj.get("arrows", []),
        "lists": obj.get("lists", []),
    }
