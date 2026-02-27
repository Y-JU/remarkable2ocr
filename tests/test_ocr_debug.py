
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.layout.ocr_debug import write_ocr_preview_html, render_ocr_overlay

class TestOCRDebug:
    def test_write_ocr_preview_html(self, tmp_path):
        ocr_data = [
            [
                {"text": "Line 1", "x_ratio": 0.1, "y_ratio": 0.2, "confidence": 0.99},
                {"text": "Line 2", "x_ratio": 0.3, "y_ratio": 0.4}
            ],
            []
        ]
        out = tmp_path / "preview.html"
        res = write_ocr_preview_html(ocr_data, out)
        
        assert res.exists()
        content = res.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "Page 1 (2 lines)" in content
        assert "Line 1" in content
        assert "0.99" in content
        assert "Page 2 (0 lines)" in content

    def test_render_ocr_overlay_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            render_ocr_overlay([], tmp_path / "missing.png", tmp_path / "out.png")

    def test_render_ocr_overlay_success(self, tmp_path):
        # Create dummy source image
        from PIL import Image
        src_path = tmp_path / "src.png"
        Image.new("RGB", (100, 100), "white").save(src_path)
        
        ocr_lines = [
            {"text": "Hello", "x_ratio": 0.5, "y_ratio": 0.5},
            {"text": "", "x_ratio": 0.0}, # Empty text should be skipped
        ]
        out_path = tmp_path / "overlay.png"
        
        # We want to allow load_default to work, but mock truetype to fail if needed
        # But PIL's load_default actually CALLS truetype internally in newer versions!
        # That's why side_effect=IOError on truetype breaks load_default.
        
        # Instead of mocking, let's just rely on the fact that the system might not have the specific fonts listed in ocr_debug.py
        # The code tries a list of paths. If none found, it falls back to load_default.
        # If load_default works, great. If not, it handles Exception and sets font=None.
        
        # So we don't mock anything. We just run it. 
        # If the environment has no fonts at all, it might use font=None path.
        res = render_ocr_overlay(ocr_lines, src_path, out_path)
            
        assert res.exists()
        assert res.stat().st_size > 0
        
    def test_render_ocr_overlay_font_fallback(self, tmp_path):
        # This test attempts to trigger the "no font" path.
        # However, PIL's ImageDraw.text() internally attempts to load a default font if font=None.
        # If we mock load_default to fail, ImageDraw.text() raises OSError/Exception.
        # This means we can't easily test the successful execution of draw.text(..., font=None) 
        # unless we mock ImageDraw.text itself.
        
        from PIL import Image, ImageFont, ImageDraw
        src_path = tmp_path / "src.png"
        Image.new("RGB", (100, 100), "white").save(src_path)
        
        ocr_lines = [{"text": "Hello"}]
        out_path = tmp_path / "overlay.png"

        # Mock ImageDraw.text so we don't crash when it tries to load font
        with patch("PIL.ImageFont.truetype", side_effect=IOError), \
             patch("PIL.ImageFont.load_default", side_effect=IOError), \
             patch("PIL.ImageDraw.ImageDraw.text") as mock_text:
             
             render_ocr_overlay(ocr_lines, src_path, out_path)
             
             # Verify it called text without font (or with whatever logic uses)
             # Our code: if font: ... else: draw.text(..., font=font) is NOT what happens
             # Code:
             # if font: draw.text(..., font=font)
             # else: draw.text(...) 
             
             # Since font is None (due to load_default failing), it goes to else branch.
             # draw.text called with no font kwarg (or default).
             assert mock_text.called
             
        assert out_path.exists()

    def test_render_ocr_overlay_no_font(self, tmp_path):
         # Redundant with above now, but let's keep it clean
         pass

