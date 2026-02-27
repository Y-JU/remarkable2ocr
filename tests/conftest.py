"""Pytest configuration and shared fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def mock_ocr_lines() -> list[dict]:
    """Minimal OCR-like data for layout tests."""
    return [
        {"text": "Line one", "y_ratio": 0.2, "x_ratio": 0.3},
        {"text": "Line two", "y_ratio": 0.5, "x_ratio": 0.3, "links": [0]},
    ]


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Avoid loading project .env in tests unless explicitly set."""
    for key in ("DATA_DIR", "GOOGLE_API_KEY", "REMARKABLE_HOST"):
        monkeypatch.delenv(key, raising=False)
