"""Layout: OCR data -> SVG/HTML (multi-page, draggable)."""
from .chart_schema import ChartSchema, CHART_SCHEMA_INSTRUCTION
from .semantic_chart import semantic_parse
from .render_chart import render_to_html, render_to_svg
from .ocr_layout import render_ocr_to_html, render_ocr_to_html_multi
from .ocr_debug import write_ocr_preview_html, render_ocr_overlay

__all__ = [
    "ChartSchema",
    "CHART_SCHEMA_INSTRUCTION",
    "semantic_parse",
    "render_to_html",
    "render_to_svg",
    "render_ocr_to_html",
    "render_ocr_to_html_multi",
    "write_ocr_preview_html",
    "render_ocr_overlay",
]
