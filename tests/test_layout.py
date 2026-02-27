"""Tests for layout generation (no Gemini)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.layout import render_ocr_to_html, render_ocr_to_html_multi, write_ocr_preview_html


def test_render_ocr_to_html(mock_ocr_lines: list[dict], tmp_path: Path) -> None:
    """render_ocr_to_html produces an HTML file with expected content."""
    out = tmp_path / "layout.html"
    result = render_ocr_to_html(mock_ocr_lines, out)
    assert result == out
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "Line one" in html
    assert "Line two" in html
    assert "ocr-page" in html
    assert "ocr-line" in html


def test_render_ocr_to_html_multi(mock_ocr_lines: list[dict], tmp_path: Path) -> None:
    """render_ocr_to_html_multi produces multi-page HTML."""
    out = tmp_path / "multi.html"
    result = render_ocr_to_html_multi([mock_ocr_lines], out)
    assert result == out
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "Page 1" in html
    assert "Line one" in html


def test_render_ocr_to_html_multi_two_pages(mock_ocr_lines: list[dict], tmp_path: Path) -> None:
    """Multi-page layout has two sections for two pages."""
    out = tmp_path / "two.html"
    page2 = [{"text": "Second page", "y_ratio": 0.5, "x_ratio": 0.5}]
    render_ocr_to_html_multi([mock_ocr_lines, page2], out)
    html = out.read_text(encoding="utf-8")
    assert "Page 1" in html
    assert "Page 2" in html
    assert "Second page" in html


def test_write_ocr_preview_html(mock_ocr_lines: list[dict], tmp_path: Path) -> None:
    """write_ocr_preview_html produces debug preview."""
    out = tmp_path / "preview.html"
    write_ocr_preview_html([mock_ocr_lines], out)
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "Line one" in html
