
import struct
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.remarkable.render import (
    _read_rm_version,
    _parse_rm_strokes,
    _parse_rm_v6_strokes,
    _read_rm_version_and_layers,
    _stroke_color_to_rgb,
    get_page_dimensions_from_content,
    render_rm_to_png,
    render_notebook_pages,
    RM2_WIDTH,
    RM2_HEIGHT,
)
from src.remarkable.parse import NotebookInfo, PageInfo

HEADER_V3 = b"reMarkable .lines file, version=3    "
HEADER_V5 = b"reMarkable .lines file, version=5    "
HEADER_V6 = b"reMarkable .lines file, version=6    "

def test_read_rm_version_invalid_header():
    with pytest.raises(ValueError, match="Invalid .rm header"):
        _read_rm_version(b"Invalid header data", 0)

def test_read_rm_version_valid():
    assert _read_rm_version(HEADER_V3, 0) == 3
    assert _read_rm_version(HEADER_V5, 0) == 5
    assert _read_rm_version(HEADER_V6, 0) == 6
    # Test default fallback (though header check might prevent this in practice,
    # the code has a fallback)
    header_unknown = b"reMarkable .lines file, version=9    "
    assert _read_rm_version(header_unknown, 0) == 3

def test_read_rm_version_and_layers_v6_error():
    with pytest.raises(ValueError, match="v6 uses _parse_rm_v6_strokes"):
        _read_rm_version_and_layers(HEADER_V6, 0)

def test_read_rm_version_and_layers_short_file():
    # Header is 43 bytes. Need +4 bytes for n_layers
    data = HEADER_V5
    with pytest.raises(ValueError, match=".rm file too short"):
        _read_rm_version_and_layers(data, 0)

def test_get_page_dimensions_from_content_errors(tmp_path):
    # Non-existent file
    assert get_page_dimensions_from_content(tmp_path / "missing.json") == (RM2_WIDTH, RM2_HEIGHT)
    
    # Invalid JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid", encoding="utf-8")
    assert get_page_dimensions_from_content(bad_json) == (RM2_WIDTH, RM2_HEIGHT)
    
    # Valid JSON but missing keys
    empty_json = tmp_path / "empty.json"
    empty_json.write_text("{}", encoding="utf-8")
    assert get_page_dimensions_from_content(empty_json) == (RM2_WIDTH, RM2_HEIGHT)

def test_stroke_color_to_rgb():
    # Known color
    assert _stroke_color_to_rgb(0) == (0, 0, 0)
    # Unknown color (default black)
    assert _stroke_color_to_rgb(999) == (0, 0, 0)
    # ARGB handling
    # ARGB: Alpha=255 (0xFF), Red=255, Green=0, Blue=0
    # 0xFF0000FF (Little Endian?) No, input is int.
    # 0xFF << 24 | 0xFF << 16 | 0x00 << 8 | 0x00
    red_opaque = (255 << 24) | (255 << 16)
    # However, the function checks: if (color_val >> 24) >= 0x80 or color_val > 0x00FFFFFF
    # Let's test a high alpha value
    assert _stroke_color_to_rgb(red_opaque) == (255, 0, 0)
    
    # Test semi-transparent
    # Alpha = 128 (~0.5)
    # Result should be blended with white (255, 255, 255)
    # r = r * a + 255 * (1-a)
    # if r=0, g=0, b=0 (black), alpha=128
    # r = 0 + 255 * 0.5 = 127
    semi_black = (128 << 24)
    r, g, b = _stroke_color_to_rgb(semi_black)
    assert 120 <= r <= 135  # Approximate check

def test_parse_rm_strokes_v3_single_point():
    # Construct a minimal v3 body with 1 layer, 1 stroke, 1 point
    # V3 Stroke: pen(I), color(I), unk1(I), width(f), n_seg(I)
    # Segment: x, y, speed, dir, w, press (6 floats)
    n_layers = 1
    n_strokes = 1
    stroke_header = struct.pack("<IIIfI", 1, 0, 0, 2.0, 1) # 1 segment
    segment = struct.pack("<ffffff", 100.0, 200.0, 0.0, 0.0, 2.0, 0.5)
    
    data = struct.pack("<I", n_strokes) + stroke_header + segment
    
    strokes, _ = _parse_rm_strokes(data, 0, n_layers, version=3)
    assert len(strokes) == 1
    points, color = strokes[0]
    # Single point should be duplicated
    assert len(points) == 2
    assert points[0] == (100.0, 200.0)
    assert points[1] == (100.0, 200.0)

def test_parse_rm_v6_strokes_empty():
    # Test empty or invalid v6 body
    data = HEADER_V6
    strokes, bbox = _parse_rm_v6_strokes(data)
    assert strokes == []
    assert bbox == (0, 0, RM2_WIDTH, RM2_HEIGHT)

def test_render_notebook_pages_error(tmp_path):
    # Setup a notebook with a page that fails to render
    nb_dir = tmp_path / "nb"
    nb_dir.mkdir()
    rm_file = nb_dir / "0.rm"
    rm_file.write_bytes(b"invalid data")
    
    # Create thumbnail to test fallback
    thumb_file = nb_dir / "0.thumbnails" / "0.jpg" # Usually .jpg or .png
    # But code checks page.thumbnail_path
    # Let's mock PageInfo
    page = MagicMock(spec=PageInfo)
    page.index = 0
    page.rm_path = rm_file
    page.thumbnail_path = tmp_path / "thumb.png"
    page.thumbnail_path.write_bytes(b"fake image")
    
    notebook = MagicMock(spec=NotebookInfo)
    notebook.pages = [page]
    notebook.content_path = None
    
    out_dir = tmp_path / "out"
    
    paths = render_notebook_pages(notebook, out_dir)
    
    assert len(paths) == 1
    assert paths[0].name == "page_0.png"
    # Content should be from thumbnail (fallback)
    assert paths[0].read_bytes() == b"fake image"

def test_render_notebook_pages_no_rm_only_thumb(tmp_path):
    page = MagicMock(spec=PageInfo)
    page.index = 0
    page.rm_path = None
    page.thumbnail_path = tmp_path / "thumb.png"
    page.thumbnail_path.write_bytes(b"fake image")
    
    notebook = MagicMock(spec=NotebookInfo)
    notebook.pages = [page]
    
    out_dir = tmp_path / "out"
    paths = render_notebook_pages(notebook, out_dir)
    assert len(paths) == 1
    assert paths[0].read_bytes() == b"fake image"

def test_render_rm_to_png_v6_with_content_scaling(tmp_path):
    # Mock _parse_rm_file to return v6-like data with bbox
    with patch("src.remarkable.render._parse_rm_file") as mock_parse:
        # strokes, bbox
        # bbox is (min_x, min_y, max_x, max_y)
        mock_parse.return_value = (
            [([(10, 10), (20, 20)], 0)], 
            (0, 0, 100, 100)
        )
        
        rm_path = tmp_path / "test.rm"
        out_path = tmp_path / "test.png"
        
        # content file with custom dimensions
        content_path = tmp_path / "content.json"
        content_path.write_text('{"customZoomPageWidth": 200, "customZoomPageHeight": 300}')
        
        render_rm_to_png(rm_path, out_path, content_path=content_path)
        
        assert out_path.exists()

def test_parse_rm_v6_strokes_valid():
    LINE_DEF_FLAG = 0x5020200
    flag_b = struct.pack("<I", LINE_DEF_FLAG)
    
    # Points
    # x=10, y=20. Stride 14.
    # [x:4] [y:4] [pad:6]
    p1 = struct.pack("<ff", 10.0, 20.0) + b"\x00"*6
    p2 = struct.pack("<ff", 30.0, 40.0) + b"\x00"*6
    points_data = p1 + p2
    len_pt = len(points_data) # 28
    
    # Body
    # Color at -18 from \x5c
    # [color 4] [pad 14] [\x5c] [len_pt 4] [points...]
    color = 2 # Red?
    pad = b"\x00" * 14
    marker = b"\x5c"
    len_pt_b = struct.pack("<I", len_pt)
    
    body_content = struct.pack("<I", color) + pad + marker + len_pt_b + points_data
    
    # body = data[i+8 : end]
    # i is flag start.
    # [len_body] [flag] [unk 4] [body_content]
    
    unk = b"\x00" * 4
    len_body = len(body_content)
    
    data = struct.pack("<I", len_body) + flag_b + unk + body_content
    
    strokes, bbox = _parse_rm_v6_strokes(data)
    
    assert len(strokes) == 1
    pts, c = strokes[0]
    assert c == 2
    assert len(pts) == 2
    # x is adjusted by half_w (1404//2 = 702)
    # x_px = x + half_w
    assert pts[0] == (10.0 + 702, 20.0)
    assert pts[1] == (30.0 + 702, 40.0)
    
    # Bounding box should match
    min_x, min_y, max_x, max_y = bbox
    assert min_x == 10.0 + 702
    assert max_x == 30.0 + 702
    assert min_y == 20.0
    assert max_y == 40.0

def test_parse_rm_v6_strokes_color_boundary():
    # Test case where \x5c is found early in the body, so color lookup returns 0
    # idx_5c < 18.
    
    LINE_DEF_FLAG = 0x5020200
    flag_b = struct.pack("<I", LINE_DEF_FLAG)
    
    # Points
    p1 = struct.pack("<ff", 10.0, 20.0) + b"\x00"*6
    points_data = p1
    len_pt = len(points_data)
    
    # Body
    # Make marker appear at index 0
    marker = b"\x5c"
    len_pt_b = struct.pack("<I", len_pt)
    
    body_content = marker + len_pt_b + points_data
    
    # body = data[i+8 : end]
    unk = b"\x00" * 4
    len_body = len(body_content)
    
    data = struct.pack("<I", len_body) + flag_b + unk + body_content
    
    strokes, bbox = _parse_rm_v6_strokes(data)
    
    assert len(strokes) == 1
    pts, c = strokes[0]
    assert c == 0 # Default color
