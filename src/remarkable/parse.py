"""
Parse local data/xochitl layout; list notebooks and page info.
"""
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class PageInfo:
    """Single page info."""
    page_id: str
    index: int  # 0-based
    rm_path: Path | None
    thumbnail_path: Path | None


@dataclass
class NotebookInfo:
    """Notebook info."""
    uuid: str
    visible_name: str
    file_type: str
    page_count: int
    pages: list[PageInfo] = field(default_factory=list)
    metadata_path: Path | None = None
    content_path: Path | None = None


def get_xochitl_root(base: Path) -> Path:
    if (base / "xochitl").is_dir():
        return base / "xochitl"
    return base


def list_notebooks(xochitl_path: Path) -> list[NotebookInfo]:
    xochitl_path = Path(xochitl_path)
    if not xochitl_path.is_dir():
        return []

    notebooks: list[NotebookInfo] = []
    for meta_path in xochitl_path.glob("*.metadata"):
        uuid = meta_path.stem
        try:
            raw = meta_path.read_text(encoding="utf-8")
            meta = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            continue
        if meta.get("type") != "DocumentType":
            continue
        content_path = xochitl_path / f"{uuid}.content"
        if not content_path.is_file():
            continue
        try:
            content_raw = content_path.read_text(encoding="utf-8")
            content = json.loads(content_raw)
        except (json.JSONDecodeError, OSError):
            continue
        if content.get("fileType") != "notebook":
            continue

        page_count = content.get("pageCount", 0)
        c_pages = content.get("cPages") or {}
        pages_list = c_pages.get("pages") or content.get("pages") or []
        pages: list[PageInfo] = []
        for i, p in enumerate(pages_list):
            page_id = p.get("id") if isinstance(p, dict) else None
            if not page_id:
                continue
            rm_path = xochitl_path / uuid / f"{page_id}.rm"
            if not rm_path.is_file():
                rm_path = None
            thumb_path = xochitl_path / f"{uuid}.thumbnails" / f"{page_id}.png"
            if not thumb_path.is_file():
                thumb_path = None
            pages.append(
                PageInfo(
                    page_id=page_id,
                    index=i,
                    rm_path=rm_path,
                    thumbnail_path=thumb_path,
                )
            )

        notebooks.append(
            NotebookInfo(
                uuid=uuid,
                visible_name=meta.get("visibleName", ""),
                file_type=content.get("fileType", "notebook"),
                page_count=page_count,
                pages=pages,
                metadata_path=meta_path,
                content_path=content_path,
            )
        )

    return notebooks


def get_notebook(xochitl_path: Path, uuid: str | None = None, name: str | None = None) -> NotebookInfo | None:
    notebooks = list_notebooks(xochitl_path)
    if uuid:
        for nb in notebooks:
            if nb.uuid == uuid:
                return nb
    if name:
        for nb in notebooks:
            if nb.visible_name == name:
                return nb
    return None
