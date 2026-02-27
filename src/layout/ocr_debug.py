"""
OCR debug: 1) HTML preview of recognition results and coordinates; 2) overlay image for comparison.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _esc(s: str) -> str:
    return html.escape(str(s))


def write_ocr_preview_html(all_ocr_by_page: list[list[dict[str, Any]]], out_path: Path) -> Path:
    """
    Write ocr_preview.html: per-page table of OCR rows (text, x_ratio, y_ratio, confidence).
    """
    out_path = Path(out_path)
    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>OCR results and coordinates</title>
<style>
  body { font-family: sans-serif; margin: 1rem; background: #fafafa; }
  h1 { font-size: 1.2rem; }
  h2 { font-size: 1rem; margin-top: 1.5rem; }
  table { border-collapse: collapse; width: 100%; max-width: 900px; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }
  th { background: #333; color: #fff; }
  tr:nth-child(even) { background: #f9f9f9; }
  .num { font-variant-numeric: tabular-nums; }
  code { background: #eee; padding: 0.1em 0.3em; border-radius: 3px; }
</style>
</head>
<body>
<h1>OCR results and coordinates</h1>
<p>Per-page <code>text</code>, <code>x_ratio</code>, <code>y_ratio</code>, <code>confidence</code> for debugging.</p>
""")
    for page_idx, ocr_lines in enumerate(all_ocr_by_page):
        parts.append(f'<h2>Page {page_idx + 1} ({len(ocr_lines)} lines)</h2>')
        parts.append("""<table>
<thead><tr><th>#</th><th>text</th><th>x_ratio</th><th>y_ratio</th><th>confidence</th></tr></thead>
<tbody>
""")
        for i, row in enumerate(ocr_lines):
            text = row.get("text", "")
            x = row.get("x_ratio", 0)
            y = row.get("y_ratio", 0)
            conf = row.get("confidence", "")
            parts.append(
                f'<tr><td class="num">{i}</td><td>{_esc(text)}</td><td class="num">{x}</td><td class="num">{y}</td><td>{_esc(str(conf))}</td></tr>\n'
            )
        parts.append("</tbody></table>\n")
    parts.append("</body></html>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(parts), encoding="utf-8")
    return out_path


def render_ocr_overlay(
    ocr_lines: list[dict[str, Any]],
    source_image_path: Path,
    out_path: Path,
    *,
    font_size_ratio: float = 0.02,
) -> Path:
    """
    Draw OCR text at x_ratio/y_ratio on a canvas same size as source image; save as overlay for debugging.
    """
    from PIL import Image, ImageDraw, ImageFont

    out_path = Path(out_path)
    src = Path(source_image_path)
    if not src.is_file():
        raise FileNotFoundError(f"Source image not found: {src}")

    img = Image.open(src).convert("RGB")
    w, h = img.size
    overlay = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(overlay)

    font_size = max(12, int(min(w, h) * font_size_ratio))
    font = None
    for try_path in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]:
        try:
            font = ImageFont.truetype(try_path, font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    for row in ocr_lines:
        text = row.get("text", "") or ""
        if not text:
            continue
        x_ratio = max(0.0, min(1.0, float(row.get("x_ratio", 0.5))))
        y_ratio = max(0.0, min(1.0, float(row.get("y_ratio", 0.5))))
        px = int(x_ratio * (w - 20)) + 10
        py = int(y_ratio * (h - 20)) + 10
        if font:
            draw.text((px, py), text, fill=(0, 0, 0), font=font)
        else:
            draw.text((px, py), text, fill=(0, 0, 0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(out_path, "PNG")
    return out_path
