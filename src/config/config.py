"""
Load .env from project root; expose DATA_DIR, GOOGLE_API_KEY, REMARKABLE_*.
Call load_env() before using in main or other modules.
"""
from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    """Project root (directory containing data/, src/)."""
    p = Path(__file__).resolve()
    # src/config/config.py -> two levels up
    for _ in range(3):
        p = p.parent
        if (p / "data").is_dir() or (p / "src").is_dir():
            return p
    return Path.cwd()


def load_env() -> None:
    """Load env vars from project root .env if present."""
    root = _project_root()
    env_file = root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'\"")
        if k and v:
            os.environ.setdefault(k, v)


def get_data_dir() -> Path:
    """xochitl data root; default <project_root>/data/xochitl."""
    load_env()
    root = _project_root()
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        return Path(data_dir)
    return root / "data" / "xochitl"


def get_ocr_api_key() -> str | None:
    """OCR API key (OCR_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY)."""
    load_env()
    return (
        os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("OCR_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or None
    )


def get_ocr_base_url() -> str | None:
    """OCR API base URL (OCR_BASE_URL or OPENAI_BASE_URL)."""
    load_env()
    has_google_key = os.environ.get("GOOGLE_API_KEY") is not None
    return has_google_key and "https://generativelanguage.googleapis.com/v1beta/openai/" or os.environ.get("OCR_BASE_URL") or os.environ.get("OPENAI_BASE_URL")


def get_ocr_model_name() -> str:
    """OCR model name (OCR_MODEL_NAME or OPENAI_MODEL_NAME). Default: gpt-4o."""
    load_env()
    has_google_key = os.environ.get("GOOGLE_API_KEY") is not None
    return (
        has_google_key and (os.environ.get("GOOGLE_MODEL_NAME") or "gemini-2.0-flash")
        or os.environ.get("OCR_MODEL_NAME")
        or os.environ.get("OPENAI_MODEL_NAME")
    )


def get_remarkable_host() -> str:
    """reMarkable device host for SSH/rsync (e.g. 10.11.99.1)."""
    load_env()
    return os.environ.get("REMARKABLE_HOST", "10.11.99.1")


def get_remarkable_user() -> str:
    """SSH user on reMarkable (default root)."""
    load_env()
    return os.environ.get("REMARKABLE_USER", "root")


def get_remarkable_xochitl_path() -> str:
    """Path to xochitl directory on the reMarkable device."""
    load_env()
    return os.environ.get(
        "REMARKABLE_XOCHITL_PATH",
        "/home/root/.local/share/remarkable/xochitl",
    )
