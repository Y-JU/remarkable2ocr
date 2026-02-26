"""Config: load .env, expose DATA_DIR, GOOGLE_API_KEY, REMARKABLE_*, etc."""
from .config import (
    load_env,
    get_data_dir,
    get_ocr_api_key,
    get_remarkable_host,
    get_remarkable_user,
    get_remarkable_xochitl_path,
)

__all__ = [
    "load_env",
    "get_data_dir",
    "get_ocr_api_key",
    "get_remarkable_host",
    "get_remarkable_user",
    "get_remarkable_xochitl_path",
]
