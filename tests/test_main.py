"""Tests for main entry and helpers."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_safe_notebook_name() -> None:
    """_safe_notebook_name sanitizes for filesystem."""
    from main import _safe_notebook_name

    assert _safe_notebook_name("My Notebook") == "My_Notebook"
    assert _safe_notebook_name("a/b*c") == "abc"
    assert _safe_notebook_name("  x  ") == "x"
    assert _safe_notebook_name("") == "unnamed"
    assert len(_safe_notebook_name("a" * 300)) == 200


def test_main_help_exits_zero() -> None:
    """python main.py --help exits with 0."""
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "pull" in result.stdout or "--pull" in result.stdout
    assert "camera" in result.stdout or "--camera" in result.stdout
