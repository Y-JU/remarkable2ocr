"""Tests for XMind mind map export from OCR layout and relationship validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.layout import build_xmind, load_xmind_topic_titles, load_xmind_parent_child_pairs


def test_main_help_shows_xmind() -> None:
    """main.py --help mentions --xmind."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--xmind" in result.stdout


def test_build_xmind_creates_file(tmp_path: Path) -> None:
    """build_xmind produces a .xmind file with OCR content."""
    ocr_pages = [[
        {"text": "Root", "y_ratio": 0.2, "x_ratio": 0.5, "links": [1, 2]},
        {"text": "Child A", "y_ratio": 0.4, "x_ratio": 0.3},
        {"text": "Child B", "y_ratio": 0.4, "x_ratio": 0.7, "links": [3]},
        {"text": "Grandchild", "y_ratio": 0.6, "x_ratio": 0.7},
    ]]
    out = tmp_path / "project.xmind"
    build_xmind(ocr_pages, out, sheet_title="Test")
    assert out.is_file()
    titles = load_xmind_topic_titles(out)
    assert "Root" in titles
    assert "Child A" in titles
    assert "Child B" in titles
    assert "Grandchild" in titles


def test_xmind_relationship_validation(tmp_path: Path) -> None:
    """Mind map parent-child relationships match OCR links."""
    # OCR: 0=Root (links to 1,2), 1=A, 2=B (links to 3), 3=Grandchild
    ocr_pages = [[
        {"text": "Root", "y_ratio": 0.2, "x_ratio": 0.5, "links": [1, 2]},
        {"text": "Child A", "y_ratio": 0.4, "x_ratio": 0.3},
        {"text": "Child B", "y_ratio": 0.4, "x_ratio": 0.7, "links": [3]},
        {"text": "Grandchild", "y_ratio": 0.6, "x_ratio": 0.7},
    ]]
    out = tmp_path / "validate.xmind"
    build_xmind(ocr_pages, out)

    titles = load_xmind_topic_titles(out)
    expected_texts = {"Root", "Child A", "Child B", "Grandchild"}
    assert expected_texts.issubset(set(titles)), f"Missing OCR texts in mind map: {expected_texts - set(titles)}"

    pairs = load_xmind_parent_child_pairs(out)
    # OCR links: Root->Child A, Root->Child B, Child B->Grandchild
    expected_pairs = {("Root", "Child A"), ("Root", "Child B"), ("Child B", "Grandchild")}
    pair_set = set(pairs)
    assert expected_pairs.issubset(pair_set), f"Expected relationships {expected_pairs} not found in {pair_set}"


def test_build_xmind_empty_creates_root_only(tmp_path: Path) -> None:
    """Empty OCR produces xmind with single root (no content)."""
    out = tmp_path / "empty.xmind"
    build_xmind([], out)
    assert out.is_file()
    titles = load_xmind_topic_titles(out)
    assert len(titles) >= 1
    assert "(No content)" in titles or titles[0] == "(No content)"
