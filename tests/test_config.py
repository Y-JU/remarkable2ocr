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


def test_google_env_priority(monkeypatch) -> None:
    """
    Test case 1 & 2:
    - If GOOGLE_API_KEY is set, it should be used.
    - Base URL should be Google's OpenAI compatible endpoint.
    - Model should default to gemini-2.0-flash if not specified.
    """
    from src.config import get_ocr_api_key, get_ocr_base_url, get_ocr_model_name

    # Case 1: Only GOOGLE_API_KEY set
    monkeypatch.delenv("OCR_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OCR_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OCR_MODEL_NAME", raising=False)
    monkeypatch.delenv("OPENAI_MODEL_NAME", raising=False)
    monkeypatch.delenv("GOOGLE_MODEL_NAME", raising=False)
    
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    
    assert get_ocr_api_key() == "google-key"
    assert get_ocr_base_url() == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert get_ocr_model_name() == "gemini-2.0-flash"

    # Case 2: GOOGLE_API_KEY + others set (Google should take precedence for key/base_url logic as implemented)
    # Note: The current implementation of get_ocr_api_key checks GOOGLE_API_KEY first.
    monkeypatch.setenv("OCR_API_KEY", "ocr-key")
    monkeypatch.setenv("OCR_BASE_URL", "ocr-url")
    monkeypatch.setenv("OCR_MODEL_NAME", "ocr-model")
    
    assert get_ocr_api_key() == "google-key"
    # Logic in get_ocr_base_url checks `if os.environ.get("GOOGLE_API_KEY")` then returns google url
    assert get_ocr_base_url() == "https://generativelanguage.googleapis.com/v1beta/openai/"
    # Logic in get_ocr_model_name checks `if os.environ.get("GOOGLE_API_KEY")` then returns google model (default or specific)
    assert get_ocr_model_name() == "gemini-2.0-flash"

    # Check if GOOGLE_MODEL_NAME overrides default
    monkeypatch.setenv("GOOGLE_MODEL_NAME", "gemini-1.5-pro")
    assert get_ocr_model_name() == "gemini-1.5-pro"


def test_no_google_env_fallback(monkeypatch) -> None:
    """
    Test case 3:
    - If GOOGLE_API_KEY is NOT set, other env vars should be used.
    """
    from src.config import get_ocr_api_key, get_ocr_base_url, get_ocr_model_name
    import os

    # Mock os.environ.get to ignore system env vars entirely for the keys we care about
    # This is more robust than deleting env vars because load_env() might re-populate them from a local .env file
    
    original_environ_get = os.environ.get

    def mock_environ_get(key, default=None):
        if key in ["GOOGLE_API_KEY", "OCR_API_KEY", "OCR_BASE_URL", "OCR_MODEL_NAME", 
                   "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL_NAME", "GOOGLE_MODEL_NAME"]:
            # Only return values set in our mock store
            return mock_env_store.get(key, default)
        return original_environ_get(key, default)

    mock_env_store = {}
    
    with monkeypatch.context() as m:
        m.setattr(os.environ, "get", mock_environ_get)
        m.setattr("src.config.load_env", lambda: None)
        
        # Subcase 3a: OCR_* vars set
        mock_env_store["OCR_API_KEY"] = "ocr-key"
        mock_env_store["OCR_BASE_URL"] = "ocr-url"
        mock_env_store["OCR_MODEL_NAME"] = "ocr-model"
        
        assert get_ocr_api_key() == "ocr-key"
        assert get_ocr_base_url() == "ocr-url"
        assert get_ocr_model_name() == "ocr-model"
        
        # Subcase 3b: OPENAI_* vars set (fallback)
        del mock_env_store["OCR_API_KEY"]
        del mock_env_store["OCR_BASE_URL"]
        del mock_env_store["OCR_MODEL_NAME"]
        
        mock_env_store["OPENAI_API_KEY"] = "openai-key"
        mock_env_store["OPENAI_BASE_URL"] = "openai-url"
        mock_env_store["OPENAI_MODEL_NAME"] = "openai-model"
        
        assert get_ocr_api_key() == "openai-key"
        assert get_ocr_base_url() == "openai-url"
        assert get_ocr_model_name() == "openai-model"

