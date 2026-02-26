"""
Render .rm stroke data to PNG. Supports v3/v5/v6, .content dimensions, stroke colors.
"""
from __future__ import annotations

import json
import shutil
import struct
from pathlib import Path
from typing import List, Tuple, Optional

from .parse import NotebookInfo, PageInfo

RM2_WIDTH = 1404
RM2_HEIGHT = 1872

StrokeWithColor = Tuple[List[Tuple[float, float]], int]

STROKE_COLOR_MAP = {
    0: (0, 0, 0),
    1: (128, 128, 128),
    2: (255, 255, 255),
    3: (255, 235, 156),
    4: (174, 214, 241),
    5: (183, 228, 199),
    6: (255, 201, 201),
    7: (220, 80, 80),
    8: (100, 149, 237),
    9: (255, 200, 100),
    10: (200, 162, 200),
}


def _argb_to_rgb(argb: int) -> Tuple[int, int, int]:
    r = (argb >> 16) & 0xFF
    g = (argb >> 8) & 0xFF
    b = argb & 0xFF
    a = (argb >> 24) & 0xFF
    if a < 255 and a > 0:
        r = int(r * (a / 255) + 255 * (1 - a / 255))
        g = int(g * (a / 255) + 255 * (1 - a / 255))
        b = int(b * (a / 255) + 255 * (1 - a / 255))
    return (r, g, b)


def _stroke_color_to_rgb(color_val: int) -> Tuple[int, int, int]:
    if color_val in STROKE_COLOR_MAP:
        return STROKE_COLOR_MAP[color_val]
    if (color_val >> 24) >= 0x80 or color_val > 0x00FFFFFF:
        return _argb_to_rgb(color_val)
    return (0, 0, 0)


def get_page_dimensions_from_content(content_path: Optional[Path] = None) -> Tuple[int, int]:
    if not content_path or not content_path.is_file():
        return (RM2_WIDTH, RM2_HEIGHT)
    try:
        raw = content_path.read_text(encoding="utf-8")
        content = json.loads(raw)
        w = content.get("customZoomPageWidth") or RM2_WIDTH
        h = content.get("customZoomPageHeight") or RM2_HEIGHT
        return (int(w), int(h))
    except (json.JSONDecodeError, OSError, TypeError):
        return (RM2_WIDTH, RM2_HEIGHT)


HEADER_PREFIX = b"reMarkable .lines file, version="
S_LAYER = struct.Struct("<I")
S_STROKE_V3 = struct.Struct("<IIIfI")
S_STROKE_V5 = struct.Struct("<IIIfII")
S_SEGMENT = struct.Struct("<ffffff")


def _read_rm_version(data: bytes, offset: int) -> int:
    if not data[offset:].startswith(HEADER_PREFIX):
        raise ValueError("Invalid .rm header")
    off = offset + len(HEADER_PREFIX)
    ver = data[off : off + 1]
    if ver == b"3":
        return 3
    if ver == b"5":
        return 5
    if ver == b"6":
        return 6
    return 3


def _v6_find_point_array(body: bytes) -> Tuple[int, int]:
    best_n = 0
    best_start = -1
    idx = 0
    while True:
        idx = body.find(b"\x5c", idx)
        if idx < 0 or idx + 5 + 14 > len(body):
            break
        len_pt = struct.unpack_from("<I", body, idx + 1)[0]
        n_pts = len_pt // 14
        if n_pts > 0 and len_pt % 14 == 0 and idx + 5 + len_pt <= len(body):
            if n_pts > best_n:
                best_n = n_pts
                best_start = idx + 5
        idx += 1
    return (best_start, best_n)


def _v6_line_def_color(body: bytes, idx_5c: int) -> int:
    if idx_5c < 18:
        return 0
    return struct.unpack_from("<I", body, idx_5c - 18)[0]


def _parse_rm_v6_strokes(
    data: bytes,
) -> Tuple[List[StrokeWithColor], Tuple[float, float, float, float]]:
    LINE_DEF_FLAG = 0x5020200
    flag_b = struct.pack("<I", LINE_DEF_FLAG)
    half_w = RM2_WIDTH // 2
    strokes_raw: List[StrokeWithColor] = []
    all_x: List[float] = []
    all_y: List[float] = []
    pos = 0
    while True:
        i = data.find(flag_b, pos)
        if i < 0:
            break
        if i < 4:
            pos = i + 1
            continue
        len_body = struct.unpack_from("<I", data, i - 4)[0]
        if len_body <= 0 or len_body > 2 * 1024 * 1024:
            pos = i + 1
            continue
        end = i + 4 + 4 + len_body
        if end > len(data):
            pos = i + 1
            continue
        body = data[i + 8 : end]
        idx = 0
        best_n = 0
        best_start = -1
        idx_5c = -1
        while True:
            idx = body.find(b"\x5c", idx)
            if idx < 0 or idx + 5 + 14 > len(body):
                break
            len_pt = struct.unpack_from("<I", body, idx + 1)[0]
            n_pts = len_pt // 14
            if n_pts > 0 and len_pt % 14 == 0 and idx + 5 + len_pt <= len(body):
                if n_pts > best_n:
                    best_n = n_pts
                    best_start = idx + 5
                    idx_5c = idx
            idx += 1
        if best_start < 0 or idx_5c < 0:
            pos = i + 1
            continue
        color = _v6_line_def_color(body, idx_5c)
        points: List[Tuple[float, float]] = []
        for k in range(best_n):
            o = best_start + k * 14
            x, y = struct.unpack_from("<ff", body, o)
            x_px = x + half_w
            points.append((x_px, y))
            all_x.append(x_px)
            all_y.append(y)
        strokes_raw.append((points, color))
        pos = i + 1
    if not strokes_raw:
        return [], (0, 0, RM2_WIDTH, RM2_HEIGHT)
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    return strokes_raw, (min_x, min_y, max_x, max_y)


def _read_rm_version_and_layers(data: bytes, offset: int) -> Tuple[int, int, int]:
    version = _read_rm_version(data, offset)
    if version == 6:
        raise ValueError("v6 uses _parse_rm_v6_strokes")
    off = offset + 43
    if off + 4 > len(data):
        raise ValueError(".rm file too short")
    (n_layers,) = struct.unpack_from("<I", data, off)
    return version, n_layers, off + 4


def _parse_rm_strokes(
    data: bytes, offset: int, n_layers: int, version: int
) -> Tuple[List[StrokeWithColor], int]:
    strokes: List[StrokeWithColor] = []
    off = offset
    for _ in range(n_layers):
        (n_strokes,) = struct.unpack_from("<I", data, off)
        off += 4
        for _ in range(n_strokes):
            if version == 3:
                pen, color, unk1, width, n_seg = S_STROKE_V3.unpack_from(data, off)
                off += S_STROKE_V3.size
            else:
                pen, color, unk1, width, unk2, n_seg = S_STROKE_V5.unpack_from(data, off)
                off += S_STROKE_V5.size
            color_id = int(color) if color is not None else 0
            points: List[Tuple[float, float]] = []
            for _ in range(n_seg):
                x, y, speed, direction, w, pressure = S_SEGMENT.unpack_from(data, off)
                off += S_SEGMENT.size
                points.append((x, y))
            if len(points) >= 2:
                strokes.append((points, color_id))
            elif len(points) == 1:
                strokes.append(([points[0], points[0]], color_id))
    return strokes, off


def _parse_rm_file(
    rm_path: Path,
) -> Tuple[List[StrokeWithColor], Optional[Tuple[float, float, float, float]]]:
    data = rm_path.read_bytes()
    version = _read_rm_version(data, 0)
    if version == 6:
        strokes_raw, bbox = _parse_rm_v6_strokes(data)
        return strokes_raw, bbox
    version, n_layers, off = _read_rm_version_and_layers(data, 0)
    strokes, _ = _parse_rm_strokes(data, off, n_layers, version)
    return strokes, None


def _scale_v6_strokes_to_canvas(
    strokes_raw: List[StrokeWithColor],
    bbox: Tuple[float, float, float, float],
    canvas_w: int,
    canvas_h: int,
) -> List[StrokeWithColor]:
    min_x, min_y, max_x, max_y = bbox
    span_x = max_x - min_x or 1
    span_y = max_y - min_y or 1
    result: List[StrokeWithColor] = []
    for points, color in strokes_raw:
        scaled = []
        for x, y in points:
            x_px = max(0, min(canvas_w - 1, (x - min_x) / span_x * (canvas_w - 1)))
            y_px = max(0, min(canvas_h - 1, (y - min_y) / span_y * (canvas_h - 1)))
            scaled.append((float(x_px), float(y_px)))
        result.append((scaled, color))
    return result


def render_rm_to_png(
    rm_path: Path,
    out_path: Path,
    width: Optional[int] = None,
    height: Optional[int] = None,
    content_path: Optional[Path] = None,
) -> Path:
    from PIL import Image, ImageDraw

    base_w, base_h = get_page_dimensions_from_content(content_path)
    canvas_w = width if width is not None else base_w
    canvas_h = height if height is not None else base_h

    strokes_with_color, bbox = _parse_rm_file(rm_path)

    if bbox is not None:
        min_x, min_y, max_x, max_y = bbox
        content_h = max_y - min_y
        margin = 40
        if content_h > 0 and content_h + margin > canvas_h:
            canvas_h = int(content_h + margin)
        strokes_with_color = _scale_v6_strokes_to_canvas(
            strokes_with_color, bbox, canvas_w, canvas_h
        )
    else:
        clipped: List[StrokeWithColor] = []
        for points, color in strokes_with_color:
            xy = [
                (max(0, min(canvas_w - 1, int(p[0]))), max(0, min(canvas_h - 1, int(p[1]))))
                for p in points
            ]
            if len(xy) >= 2:
                clipped.append(([(float(a), float(b)) for a, b in xy], color))
        strokes_with_color = clipped

    img = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for points, color_id in strokes_with_color:
        if len(points) < 2:
            continue
        rgb = _stroke_color_to_rgb(color_id)
        xy = [(int(p[0]), int(p[1])) for p in points]
        for i in range(len(xy) - 1):
            draw.line([xy[i], xy[i + 1]], fill=rgb, width=2)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def render_notebook_pages(notebook: NotebookInfo, out_pages_dir: Path) -> list[Path]:
    """
    Render all pages of a notebook to out_pages_dir as page_0.png, page_1.png, ...
    Return list of output paths.
    """
    out_pages_dir = Path(out_pages_dir)
    out_pages_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for page in notebook.pages:
        out_path = out_pages_dir / f"page_{page.index}.png"
        if page.rm_path and page.rm_path.is_file():
            try:
                render_rm_to_png(
                    page.rm_path,
                    out_path,
                    content_path=notebook.content_path,
                )
                paths.append(out_path)
            except Exception:
                if page.thumbnail_path and page.thumbnail_path.is_file():
                    shutil.copy(page.thumbnail_path, out_path)
                    paths.append(out_path)
        elif page.thumbnail_path and page.thumbnail_path.is_file():
            shutil.copy(page.thumbnail_path, out_path)
            paths.append(out_path)
    return paths
