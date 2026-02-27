"""Tests for main entry and helpers."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


def _run_main(args: list[str], data_dir: Path | None = None) -> subprocess.CompletedProcess:
    """Run main.py with optional DATA_DIR; return CompletedProcess."""
    env = {**os.environ}
    if data_dir is not None:
        env["DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, "main.py"] + args,
        cwd=_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


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
        cwd=_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "pull" in result.stdout or "--pull" in result.stdout
    assert "camera" in result.stdout or "--camera" in result.stdout
    assert "project" in result.stdout or "--project" in result.stdout


def test_main_project_not_found_friendly_message(tmp_path: Path) -> None:
    """--project with non-existent project name exits 1 and prints a friendly message."""
    data_dir = tmp_path / "xochitl"
    data_dir.mkdir(parents=True)
    result = _run_main(["--project", "NonexistentProjectName_NoSuchNotebook"], data_dir=data_dir)
    assert result.returncode == 1
    combined = (result.stdout + "\n" + result.stderr).strip()
    assert "NonexistentProjectName_NoSuchNotebook" in combined or "not found" in combined.lower()
    assert "no notebook" in combined.lower() or "No notebook" in combined


@pytest.mark.parametrize("args", [
    [],
    ["--no-cache"],
    ["--xmind"],
    ["--no-cache", "--xmind"],
])
def test_main_no_notebooks_exits_zero(tmp_path: Path, args: list[str]) -> None:
    """With empty data dir, main.py [--no-cache] [--xmind] exits 0 (no notebooks found)."""
    data_dir = tmp_path / "xochitl"
    data_dir.mkdir(parents=True)
    result = _run_main(args, data_dir=data_dir)
    assert result.returncode == 0, f"stdout={result.stdout} stderr={result.stderr}"


def test_main_camera_no_images_exits_one(tmp_path: Path) -> None:
    """--camera with project dir that has no images exits 1 with clear message."""
    data_dir = tmp_path / "xochitl"
    camera_dir = data_dir / "camera" / "empty_project"
    camera_dir.mkdir(parents=True)
    result = _run_main(["--camera", "empty_project"], data_dir=data_dir)
    assert result.returncode == 1
    combined = (result.stdout + "\n" + result.stderr).strip()
    assert "No image found" in combined or "empty_project" in combined


def test_main_pull_fails_exits_one(tmp_path: Path) -> None:
    """--pull with unreachable host exits 1 (no hang). Use 127.0.0.1 so connection fails fast."""
    data_dir = tmp_path / "xochitl"
    data_dir.mkdir(parents=True)
    env = {
        **os.environ,
        "DATA_DIR": str(data_dir),
        "REMARKABLE_HOST": "127.0.0.1",
    }
    result = subprocess.run(
        [sys.executable, "main.py", "--pull"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    assert result.returncode == 1


@pytest.mark.parametrize("args", [
    ["--project", "SomeNotebook", "--xmind"],
    ["--no-cache", "--project", "Other"],
])
def test_main_project_not_found_with_other_flags(tmp_path: Path, args: list[str]) -> None:
    """--project NAME with --xmind or --no-cache still exits 1 when project not found."""
    data_dir = tmp_path / "xochitl"
    data_dir.mkdir(parents=True)
    result = _run_main(args, data_dir=data_dir)
    assert result.returncode == 1
    combined = (result.stdout + "\n" + result.stderr).strip()
    assert "not found" in combined.lower() or "No notebook" in combined
