#!/usr/bin/env python3
"""
Root entry: scan data/xochitl notebooks -> render -> OCR -> layout.
Supports --pull (rsync from reMarkable) and --camera (OCR a single image).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config import load_env, get_data_dir
from src.remarkable import list_notebooks, render_notebook_pages, pull_xochitl
from src.ocr import ocr_image
from src.layout import write_ocr_preview_html, render_ocr_overlay, render_ocr_to_html_multi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _safe_notebook_name(name: str) -> str:
    """Turn notebook visible name into a filesystem-safe directory name."""
    s = re.sub(r'[/\\:*?"<>|]', "", name)
    s = s.strip() or "unnamed"
    s = re.sub(r"\s+", "_", s)
    return s[:200]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scan data/xochitl notebooks -> render -> OCR -> layout. Supports --pull and --camera."
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore local OCR cache and call Gemini for every page",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull xochitl from reMarkable via SSH+rsync before processing; fail if not connected",
    )
    parser.add_argument(
        "--camera",
        metavar="PROJECT_NAME",
        default=None,
        help="Run OCR on a single image in data/xochitl/camera/PROJECT_NAME/ and output to output/PROJECT_NAME/",
    )
    args = parser.parse_args()
    use_ocr_cache = not args.no_cache

    load_env()
    data_dir = get_data_dir()

    if args.pull:
        try:
            pull_xochitl(data_dir)
        except Exception as e:
            logger.error("%s", e)
            return 1

    if not data_dir.is_dir():
        logger.error("Data directory does not exist: %s (set DATA_DIR or create data/xochitl)", data_dir)
        return 1

    output_root = _ROOT / "output"
    output_root.mkdir(parents=True, exist_ok=True)
    logger.info("Data dir: %s, output root: %s", data_dir, output_root)

    if args.camera is not None:
        return _run_camera_mode(data_dir, output_root, args.camera, use_ocr_cache)

    return _run_notebook_mode(data_dir, output_root, use_ocr_cache)


def _run_camera_mode(
    data_dir: Path,
    output_root: Path,
    project_name: str,
    use_ocr_cache: bool,
) -> int:
    """Process a single image from data/xochitl/camera/<project_name>/."""
    camera_dir = data_dir / "camera" / project_name
    if not camera_dir.is_dir():
        logger.error("Camera directory not found: %s", camera_dir)
        return 1
    images = sorted(
        p for p in camera_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        logger.error("No image found in %s (supported: %s)", camera_dir, ", ".join(IMAGE_EXTENSIONS))
        return 1
    image_path = images[0]
    out_dir = output_root / project_name
    pages_dir = out_dir / "pages"
    ocr_dir = out_dir / "ocr"
    pages_dir.mkdir(parents=True, exist_ok=True)
    ocr_dir.mkdir(parents=True, exist_ok=True)
    page_0 = pages_dir / "page_0.png"
    if image_path.suffix.lower() == ".png":
        shutil.copy2(image_path, page_0)
    else:
        try:
            from PIL import Image
            Image.open(image_path).convert("RGB").save(page_0, "PNG")
        except Exception:
            shutil.copy2(image_path, page_0)
    logger.info("Camera project: %s -> %s (image: %s)", project_name, out_dir, image_path.name)
    t0 = time.perf_counter()
    try:
        ocr_lines = ocr_image(
            page_0,
            ocr_dir,
            cache_key="page_0",
            return_confidence=True,
            use_cache=use_ocr_cache,
        )
    except Exception as e:
        logger.warning("OCR failed: %s", e)
        cache_file = ocr_dir / "page_0.json"
        if cache_file.is_file():
            try:
                ocr_lines = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                ocr_lines = []
        else:
            ocr_lines = []
    elapsed = time.perf_counter() - t0
    logger.info("  OCR page_0 done in %.2fs", elapsed)
    all_ocr = [ocr_lines]
    debug_dir = out_dir / ".debug"
    if all_ocr:
        debug_dir.mkdir(parents=True, exist_ok=True)
        try:
            write_ocr_preview_html(all_ocr, debug_dir / "ocr_preview.html")
            logger.info("  .debug: ocr_preview.html")
        except Exception as e:
            logger.warning("  Failed to write ocr_preview.html: %s", e)
        try:
            render_ocr_overlay(ocr_lines, page_0, debug_dir / "ocr_overlay_0.png")
            logger.info("  .debug: ocr_overlay_0.png")
        except Exception as e:
            logger.warning("  Failed to write ocr_overlay_0.png: %s", e)
    if not all_ocr:
        logger.warning("No OCR result, skipping layout")
        return 0
    try:
        render_ocr_to_html_multi(all_ocr, out_dir / "layout.html")
        logger.info("Layout: layout.html (1 page)")
    except Exception as e:
        logger.warning("Layout failed: %s", e)
    logger.info("Camera project %s completed in %.2fs", project_name, time.perf_counter() - t0)
    logger.info("Output: %s", output_root)
    return 0


def _run_notebook_mode(data_dir: Path, output_root: Path, use_ocr_cache: bool) -> int:
    """Scan notebooks and process each (existing flow)."""
    notebooks = list_notebooks(data_dir)
    if not notebooks:
        logger.warning("No notebooks found")
        return 0

    total_notebooks = len(notebooks)
    for idx, nb in enumerate(notebooks):
        nb_start = time.perf_counter()
        safe_name = _safe_notebook_name(nb.visible_name)
        out_dir = output_root / safe_name
        pages_dir = out_dir / "pages"
        ocr_dir = out_dir / "ocr"
        pages_dir.mkdir(parents=True, exist_ok=True)
        ocr_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Notebook %d/%d: %s -> %s", idx + 1, total_notebooks, nb.visible_name, out_dir)

        page_paths = render_notebook_pages(nb, pages_dir)
        if not page_paths:
            logger.warning("  No pages rendered, skipping OCR and layout")
            continue
        logger.info("  Pages: %d -> %s", len(page_paths), pages_dir)

        all_ocr: list[list[dict]] = []
        for i, p_path in enumerate(page_paths):
            t0 = time.perf_counter()
            try:
                ocr_lines = ocr_image(
                    p_path,
                    ocr_dir,
                    cache_key=f"page_{i}",
                    return_confidence=True,
                    use_cache=use_ocr_cache,
                )
                all_ocr.append(ocr_lines)
            except Exception as e:
                logger.warning("  OCR page_%d failed: %s", i, e)
                cache_file = ocr_dir / f"page_{i}.json"
                if cache_file.is_file():
                    try:
                        raw = cache_file.read_text(encoding="utf-8")
                        all_ocr.append(json.loads(raw))
                        logger.info("  Using cache: %s (%.2fs)", cache_file.name, time.perf_counter() - t0)
                    except Exception:
                        all_ocr.append([])
                else:
                    all_ocr.append([])
            else:
                logger.info("  Page %d/%d OCR done in %.2fs", i + 1, len(page_paths), time.perf_counter() - t0)

        debug_dir = out_dir / ".debug"
        if all_ocr:
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                write_ocr_preview_html(all_ocr, debug_dir / "ocr_preview.html")
                logger.info("  .debug: ocr_preview.html")
            except Exception as e:
                logger.warning("  Failed to write ocr_preview.html: %s", e)
            for i, (ocr_lines, p_path) in enumerate(zip(all_ocr, page_paths)):
                if not ocr_lines:
                    continue
                try:
                    render_ocr_overlay(
                        ocr_lines,
                        p_path,
                        debug_dir / f"ocr_overlay_{i}.png",
                    )
                    logger.info("  .debug: ocr_overlay_%d.png", i)
                except Exception as e:
                    logger.warning("  Failed to write ocr_overlay_%d.png: %s", i, e)

        if not all_ocr:
            logger.warning("  No OCR result, skipping layout")
            continue
        try:
            render_ocr_to_html_multi(all_ocr, out_dir / "layout.html")
            logger.info("  Layout: layout.html (%d pages)", len(all_ocr))
        except Exception as e:
            logger.warning("  Layout failed: %s", e)

        logger.info("  Notebook completed in %.2fs", time.perf_counter() - nb_start)

    logger.info("Done. Output: %s", output_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
