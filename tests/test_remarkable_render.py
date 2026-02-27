
import pytest
import struct
from pathlib import Path
from src.remarkable.render import (
    _argb_to_rgb, 
    _stroke_color_to_rgb, 
    get_page_dimensions_from_content,
    _read_rm_version,
    _v6_find_point_array
)

class TestRenderUtils:
    def test_argb_to_rgb(self):
        # Opaque red
        assert _argb_to_rgb(0xFFFF0000) == (255, 0, 0)
        # Transparent white (50% alpha)
        # r = 255*(128/255) + 255*(1-128/255) = 255
        # This function blends with white background
        r, g, b = _argb_to_rgb(0x80FF0000)
        assert r > 128  # Should be lighter than pure red
        
        # Zero alpha
        # The implementation of _argb_to_rgb extracts RGB directly first, 
        # then only modifies them if 0 < alpha < 255.
        # If alpha is 0, it returns the raw RGB values.
        # 0x00FF0000 -> A=0, R=255, G=0, B=0
        assert _argb_to_rgb(0x00FF0000) == (255, 0, 0)

    def test_stroke_color_to_rgb(self):
        # Known color map
        assert _stroke_color_to_rgb(0) == (0, 0, 0)
        assert _stroke_color_to_rgb(1) == (128, 128, 128)
        
        # ARGB fallback
        # 0xFF00FF00 (Green)
        assert _stroke_color_to_rgb(0xFF00FF00) == (0, 255, 0)
        
        # Invalid
        assert _stroke_color_to_rgb(100) == (0, 0, 0)

    def test_get_page_dimensions(self, tmp_path):
        # No file
        assert get_page_dimensions_from_content(None) == (1404, 1872)
        assert get_page_dimensions_from_content(tmp_path / "nonexistent") == (1404, 1872)
        
        # Valid JSON
        f = tmp_path / "test.content"
        f.write_text('{"customZoomPageWidth": 1000, "customZoomPageHeight": 2000}', encoding="utf-8")
        assert get_page_dimensions_from_content(f) == (1000, 2000)
        
        # Invalid JSON
        f.write_text('invalid', encoding="utf-8")
        assert get_page_dimensions_from_content(f) == (1404, 1872)

    def test_read_rm_version(self):
        header = b"reMarkable .lines file, version=3          "
        assert _read_rm_version(header, 0) == 3
        
        header = b"reMarkable .lines file, version=5          "
        assert _read_rm_version(header, 0) == 5
        
        header = b"reMarkable .lines file, version=6          "
        assert _read_rm_version(header, 0) == 6
        
        # Invalid header
        with pytest.raises(ValueError):
            _read_rm_version(b"Invalid header", 0)

    def test_v6_find_point_array(self):
        # Construct fake v6 body
        # It searches for b"\x5c"
        # Then reads len_pt (uint32)
        # Checks if len_pt % 14 == 0
        
        # Valid case: \x5c + length=28 (2 points) + 28 bytes
        # n_pts = len_pt // 14
        # so n_pts = 28 // 14 = 2
        payload = b"\x5c" + struct.pack("<I", 28) + b"\x00" * 28
        
        # The function returns (best_start, best_n)
        # NOT (n_pts, offset)
        # So we should expect (offset, n_pts) = (5, 2)
        offset, n_pts = _v6_find_point_array(payload)
        
        assert n_pts == 2
        assert offset == 5
        
        # Invalid case: too short
        payload = b"\x5c" + struct.pack("<I", 28)
        offset, n_pts = _v6_find_point_array(payload)
        assert n_pts == 0
        assert offset == -1

class TestStrokeParsing:
    def test_parse_rm_v3_strokes(self, tmp_path):
        from src.remarkable.render import _parse_rm_file
        
        # Construct minimal V3 RM file
        # Header (43 bytes)
        header = b"reMarkable .lines file, version=3          "
        # Number of layers (4 bytes) -> 1
        n_layers = struct.pack("<I", 1)
        # Number of strokes (4 bytes) -> 1
        n_strokes = struct.pack("<I", 1)
        # Stroke V3 struct: pen, color, unk1, width, n_seg
        # S_STROKE_V3 = struct.Struct("<IIIfI")
        # pen=0, color=0, unk1=0, width=2.0, n_seg=2
        stroke_header = struct.pack("<IIIfI", 0, 0, 0, 2.0, 2)
        # Segment struct: x, y, speed, direction, w, pressure
        # S_SEGMENT = struct.Struct("<ffffff")
        # Point 1: 100, 100, ...
        seg1 = struct.pack("<ffffff", 100.0, 100.0, 0.0, 0.0, 1.0, 1.0)
        # Point 2: 200, 200, ...
        seg2 = struct.pack("<ffffff", 200.0, 200.0, 0.0, 0.0, 1.0, 1.0)
        
        data = header + n_layers + n_strokes + stroke_header + seg1 + seg2
        rm_path = tmp_path / "v3.rm"
        rm_path.write_bytes(data)
        
        strokes, bbox = _parse_rm_file(rm_path)
        assert len(strokes) == 1
        points, color = strokes[0]
        assert len(points) == 2
        assert points[0] == (100.0, 100.0)
        assert points[1] == (200.0, 200.0)
        assert bbox is None

    def test_parse_rm_v5_strokes(self, tmp_path):
        from src.remarkable.render import _parse_rm_file
        
        # Construct minimal V5 RM file
        header = b"reMarkable .lines file, version=5          "
        n_layers = struct.pack("<I", 1)
        n_strokes = struct.pack("<I", 1)
        # Stroke V5 struct: pen, color, unk1, width, unk2, n_seg
        # S_STROKE_V5 = struct.Struct("<IIIfII")
        # pen=0, color=1, unk1=0, width=2.0, unk2=0, n_seg=1 (single point stroke)
        stroke_header = struct.pack("<IIIfII", 0, 1, 0, 2.0, 0, 1)
        
        seg1 = struct.pack("<ffffff", 50.0, 50.0, 0.0, 0.0, 1.0, 1.0)
        
        data = header + n_layers + n_strokes + stroke_header + seg1
        rm_path = tmp_path / "v5.rm"
        rm_path.write_bytes(data)
        
        strokes, bbox = _parse_rm_file(rm_path)
        assert len(strokes) == 1
        points, color = strokes[0]
        assert color == 1
        # Single point strokes are duplicated to make a visible dot/line of length 0
        assert len(points) == 2
        assert points[0] == (50.0, 50.0)
        assert points[1] == (50.0, 50.0)

    def test_render_rm_to_png_full_flow(self, tmp_path):
        from src.remarkable.render import render_rm_to_png
        from PIL import Image
        
        # Reuse V3 file creation
        header = b"reMarkable .lines file, version=3          "
        n_layers = struct.pack("<I", 1)
        n_strokes = struct.pack("<I", 1)
        stroke_header = struct.pack("<IIIfI", 0, 0, 0, 2.0, 2)
        seg1 = struct.pack("<ffffff", 100.0, 100.0, 0.0, 0.0, 1.0, 1.0)
        seg2 = struct.pack("<ffffff", 200.0, 200.0, 0.0, 0.0, 1.0, 1.0)
        data = header + n_layers + n_strokes + stroke_header + seg1 + seg2
        rm_path = tmp_path / "test.rm"
        rm_path.write_bytes(data)
        
        out_path = tmp_path / "out.png"
        render_rm_to_png(rm_path, out_path, width=500, height=500)
        
        assert out_path.exists()
        img = Image.open(out_path)
        assert img.size == (500, 500)

    def test_render_notebook_pages_success(self, tmp_path):
        from src.remarkable.render import render_notebook_pages
        from src.remarkable.parse import NotebookInfo, PageInfo
        
        # Create a valid RM file
        header = b"reMarkable .lines file, version=3          "
        n_layers = struct.pack("<I", 0) # 0 layers
        data = header + n_layers
        rm_path = tmp_path / "page.rm"
        rm_path.write_bytes(data)
        
        nb = NotebookInfo(
            uuid="123", visible_name="nb", file_type="notebook", page_count=1,
            pages=[
                PageInfo(page_id="p1", index=0, rm_path=rm_path, thumbnail_path=None)
            ]
        )
        
        out_dir = tmp_path / "pages"
        paths = render_notebook_pages(nb, out_dir)
        
        assert len(paths) == 1
        assert paths[0].name == "page_0.png"
        assert paths[0].exists()

    def test_render_notebook_pages_fallback(self, tmp_path):
        from src.remarkable.render import render_notebook_pages
        from src.remarkable.parse import NotebookInfo, PageInfo
        
        # Missing RM file, fallback to thumbnail
        thumb_path = tmp_path / "thumb.jpg"
        thumb_path.write_text("fake image")
        
        nb = NotebookInfo(
            uuid="123", visible_name="nb", file_type="notebook", page_count=1,
            pages=[
                PageInfo(page_id="p1", index=0, rm_path=tmp_path / "missing.rm", thumbnail_path=thumb_path)
            ]
        )
        
        out_dir = tmp_path / "pages"
        paths = render_notebook_pages(nb, out_dir)
        
        assert len(paths) == 1
        # It copies the thumbnail
        assert paths[0].read_text() == "fake image"
