"""Tests for src.config."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_get_data_dir_default(monkeypatch, tmp_path: Path) -> None:
    """Without DATA_DIR, get_data_dir returns a path ending with data/xochitl."""
    from src.config import get_data_dir

    monkeypatch.delenv("DATA_DIR", raising=False)
    got = get_data_dir()
    assert got.name == "xochitl"
    assert got.parent.name == "data"


def test_get_data_dir_from_env(monkeypatch, tmp_path: Path) -> None:
    """With DATA_DIR set, get_data_dir returns that path."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "my_data"))
    from src.config import get_data_dir

    assert get_data_dir() == tmp_path / "my_data"


def test_get_remarkable_host_default(monkeypatch) -> None:
    """Without REMARKABLE_HOST, default is 10.11.99.1."""
    monkeypatch.delenv("REMARKABLE_HOST", raising=False)
    from src.config import get_remarkable_host

    assert get_remarkable_host() == "10.11.99.1"


def test_get_remarkable_host_from_env(monkeypatch) -> None:
    """With REMARKABLE_HOST set, returns that value."""
    monkeypatch.setenv("REMARKABLE_HOST", "192.168.1.100")
    from src.config import get_remarkable_host

    assert get_remarkable_host() == "192.168.1.100"


def test_get_ocr_api_key_from_env(monkeypatch) -> None:
    """With GOOGLE_API_KEY set, get_ocr_api_key returns it."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    from src.config import get_ocr_api_key

    assert get_ocr_api_key() == "test-key-123"
