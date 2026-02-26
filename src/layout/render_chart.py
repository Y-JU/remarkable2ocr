"""
Render ChartSchema semantic JSON to HTML or SVG.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def _esc(s: str) -> str:
    return html.escape(str(s))


def _svg_esc(s: str) -> str:
    return html.escape(str(s)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_outline_items(items: list[dict], level: int = 0) -> str:
    out = []
    for item in items:
        lv = item.get("level", 1)
        text = item.get("text", "")
        tid = item.get("id", "")
        css_class = "outline-l1" if lv == 1 else "outline-l2"
        out.append(f'<div class="{css_class}" data-id="{_esc(tid)}">{_esc(text)}</div>')
        children = item.get("children") or []
        if children:
            out.append(_render_outline_items(children, lv + 1))
    return "\n".join(out)


def _render_container_html(c: dict) -> str:
    ctype = c.get("type", "rectangle")
    label = c.get("label", "")
    lines = c.get("lines") or []
    cid = c.get("id", "")
    if ctype == "ellipse":
        return f'''<div class="container container-ellipse" data-id="{_esc(cid)}">
  <svg class="ellipse-svg" viewBox="0 0 200 80" preserveAspectRatio="none">
    <ellipse cx="100" cy="40" rx="95" ry="35" fill="none" stroke="currentColor" stroke-width="2"/>
  </svg>
  <div class="container-label">{_esc(label or "")}</div>
  <div class="container-lines">{"<br>".join(_esc(ln) for ln in lines)}</div>
</div>'''
    if ctype == "longbar":
        return f'<div class="container container-longbar" data-id="{_esc(cid)}"><span class="longbar-text">{_esc(label or " ".join(lines))}</span></div>'
    return f'''<div class="container container-rectangle" data-id="{_esc(cid)}">
  <div class="container-label">{_esc(label or "")}</div>
  <div class="container-lines">{"<br>".join(_esc(ln) for ln in lines)}</div>
</div>'''


def _render_arrow_html(a: dict, index: int) -> str:
    from_id = a.get("from_id", "")
    to_id = a.get("to_id", "")
    style = a.get("style", "solid")
    direction = a.get("direction", "forward")
    stroke_dash = "stroke-dasharray: 6 4" if style == "dashed" else ""
    marker_end = "url(#arrow)" if direction != "back" else ""
    marker_start = "url(#arrow-back)" if direction == "back" else ""
    if direction == "bidirectional":
        marker_end = "url(#arrow)"
        marker_start = "url(#arrow-back)"
    return f'<line class="arrow arrow-{index}" data-from="{_esc(from_id)}" data-to="{_esc(to_id)}" x1="0" y1="0" x2="100" y2="0" style="{stroke_dash}" marker-end="{marker_end}" marker-start="{marker_start}"/>'


def _render_list_html(block: dict) -> str:
    btype = block.get("type", "bullet")
    items = block.get("items") or []
    tag = "ol" if btype == "ordered" else "ul"
    css = "list-arrow" if btype == "arrow" else ""
    lis = "".join(f"<li>{_esc(it.get('text', ''))}</li>" for it in items)
    return f'<{tag} class="chart-list {css}">{lis}</{tag}>'


def render_to_html(semantic_json: dict[str, Any], out_path: Path | str) -> Path:
    out_path = Path(out_path)
    data = dict(semantic_json)
    outline_html = _render_outline_items(data.get("outline", []))
    containers_html = "\n".join(_render_container_html(c) for c in data.get("containers", []))
    lists_html = "\n".join(_render_list_html(blk) for blk in data.get("lists", []))
    arrows = data.get("arrows", [])
    svg_arrows = "\n".join(_render_arrow_html(a, i) for i, a in enumerate(arrows))

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Chart</title>
<style>
  :root {{ font-family: sans-serif; font-size: 16px; color: #222; }}
  .chart-root {{ display: flex; flex-direction: column; max-width: 900px; margin: 0 auto; padding: 1rem; }}
  .outline {{ margin-bottom: 1rem; }}
  .outline-l1 {{ font-weight: bold; font-size: 1.1em; margin-left: 0; margin-bottom: 0.5em; }}
  .outline-l2 {{ font-size: 1em; margin-left: 1.5em; margin-bottom: 0.25em; }}
  .flow-area {{ display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }}
  .container {{ border: 2px solid #333; padding: 0.5rem 1rem; margin: 0.5rem; }}
  .container-rectangle {{ border-radius: 4px; }}
  .container-ellipse .ellipse-svg {{ width: 100%; height: auto; display: block; }}
  .container-ellipse .container-label {{ font-weight: bold; text-align: center; }}
  .container-ellipse .container-lines {{ text-align: center; font-size: 0.95em; }}
  .container-longbar {{ width: 100%; text-align: center; background: #f0f0f0; border-radius: 4px; }}
  .longbar-text {{ font-weight: bold; }}
  .container-label {{ font-weight: bold; margin-bottom: 0.25em; }}
  .container-lines {{ font-size: 0.95em; color: #444; }}
  .chart-list {{ margin: 0.5rem 0; padding-left: 1.5rem; }}
  .list-arrow {{ list-style: none; padding-left: 0; }}
  .list-arrow li::before {{ content: "→ "; font-weight: bold; }}
  .arrows-layer svg {{ overflow: visible; }}
</style>
</head>
<body>
<div class="chart-root">
  <section class="outline">{outline_html}</section>
  <section class="flow-area">{containers_html}</section>
  <section class="arrows-layer">
    <svg width="100%" height="100" viewBox="0 0 800 100" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L10,3 L0,6 z" fill="currentColor"/></marker>
        <marker id="arrow-back" markerWidth="10" markerHeight="10" refX="0" refY="3" orient="auto-start-reverse"><path d="M0,0 L10,3 L0,6 z" fill="currentColor"/></marker>
      </defs>
      {svg_arrows}
    </svg>
  </section>
  <section class="lists">{lists_html}</section>
</div>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_content, encoding="utf-8")
    return out_path


def _build_svg_content(data: dict[str, Any]) -> str:
    """Generate SVG body (no root element declaration)."""
    parts = []
    y = 24
    for item in data.get("outline", []):
        lv = item.get("level", 1)
        text = item.get("text", "")
        x = 20 if lv == 1 else 40
        font = "bold 14px sans-serif" if lv == 1 else "12px sans-serif"
        parts.append(f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{"14" if lv == 1 else "12"}" font-weight="{"bold" if lv == 1 else "normal"}" fill="#222">{_svg_esc(text)}</text>')
        y += 22
    y += 10
    for c in data.get("containers", []):
        ctype = c.get("type", "rectangle")
        label = c.get("label", "")
        lines = c.get("lines") or []
        if ctype == "ellipse":
            parts.append(f'<ellipse cx="{200}" cy="{y + 25}" rx="120" ry="28" fill="none" stroke="#333" stroke-width="2"/>')
            parts.append(f'<text x="200" y="{y + 20}" text-anchor="middle" font-size="12" font-weight="bold" fill="#222">{_svg_esc(label)}</text>')
            for i, ln in enumerate(lines):
                parts.append(f'<text x="200" y="{y + 38 + i * 14}" text-anchor="middle" font-size="11" fill="#444">{_svg_esc(ln)}</text>')
            y += 90
        elif ctype == "longbar":
            parts.append(f'<rect x="20" y="{y}" width="760" height="32" rx="4" fill="#f0f0f0" stroke="#333" stroke-width="2"/>')
            parts.append(f'<text x="400" y="{y + 21}" text-anchor="middle" font-size="12" font-weight="bold" fill="#222">{_svg_esc(label or " ".join(lines))}</text>')
            y += 44
        else:
            h = max(40, 24 + len(lines) * 16)
            parts.append(f'<rect x="20" y="{y}" width="200" height="{h}" rx="4" fill="none" stroke="#333" stroke-width="2"/>')
            parts.append(f'<text x="30" y="{y + 18}" font-size="12" font-weight="bold" fill="#222">{_svg_esc(label)}</text>')
            for i, ln in enumerate(lines):
                parts.append(f'<text x="30" y="{y + 36 + i * 16}" font-size="11" fill="#444">{_svg_esc(ln)}</text>')
            y += h + 12
    for block in data.get("lists", []):
        items = block.get("items") or []
        for it in items:
            parts.append(f'<text x="40" y="{y}" font-size="12" fill="#222">• {_svg_esc(it.get("text", ""))}</text>')
            y += 18
        y += 6
    for i, a in enumerate(data.get("arrows", [])):
        x1, y1 = 100 + i * 80, 400
        x2, y2 = 180 + i * 80, 400
        stroke_dash = ' stroke-dasharray="6 4"' if a.get("style") == "dashed" else ""
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="2" marker-end="url(#arrow)"{stroke_dash}/>')
    return "\n".join(parts)


def render_to_svg(semantic_json: dict[str, Any], out_path: Path | str) -> Path:
    """Render ChartSchema semantic JSON to an SVG file."""
    out_path = Path(out_path)
    data = dict(semantic_json)
    body = _build_svg_content(data)
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600">
  <defs>
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
      <path d="M0,0 L10,3 L0,6 z" fill="#333"/>
    </marker>
  </defs>
  <g id="outline">{body}</g>
</svg>
'''
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    return out_path
