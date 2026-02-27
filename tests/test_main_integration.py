
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from main import _run_camera_mode, _run_notebook_mode, _safe_notebook_name
from src.remarkable.parse import NotebookInfo

class TestMainIntegration:
    @pytest.fixture
    def mock_deps(self):
        with patch("main.ocr_image") as mock_ocr, \
             patch("main.write_ocr_preview_html") as mock_preview, \
             patch("main.render_ocr_overlay") as mock_overlay, \
             patch("main.render_ocr_to_html_multi") as mock_layout, \
             patch("main.list_notebooks") as mock_list, \
             patch("main.render_notebook_pages") as mock_render:
            
            mock_ocr.return_value = [{"text": "Hello"}]
            yield {
                "ocr": mock_ocr,
                "preview": mock_preview,
                "overlay": mock_overlay,
                "layout": mock_layout,
                "list": mock_list,
                "render": mock_render
            }

    def test_safe_notebook_name(self):
        assert _safe_notebook_name("My Notebook") == "My_Notebook"
        assert _safe_notebook_name("A/B:C") == "ABC"
        assert _safe_notebook_name("") == "unnamed"

    def test_run_camera_mode_no_images(self, tmp_path):
        data_dir = tmp_path / "data"
        output_root = tmp_path / "output"
        assert _run_camera_mode(data_dir, output_root, "proj1", True) == 1
        # It creates the directory if missing
        assert (data_dir / "camera" / "proj1").is_dir()

    def test_run_camera_mode_success(self, tmp_path, mock_deps):
        data_dir = tmp_path / "data"
        output_root = tmp_path / "output"
        proj_dir = data_dir / "camera" / "proj1"
        proj_dir.mkdir(parents=True)
        (proj_dir / "img1.png").touch()
        
        assert _run_camera_mode(data_dir, output_root, "proj1", True) == 0
        
        mock_deps["ocr"].assert_called()
        mock_deps["layout"].assert_called()
        
        # Verify output structure
        out_proj = output_root / "proj1"
        assert (out_proj / "pages" / "page_0.png").exists()

    def test_run_notebook_mode_no_notebooks(self, tmp_path, mock_deps):
        mock_deps["list"].return_value = []
        data_dir = tmp_path / "data"
        output_root = tmp_path / "output"
        
        assert _run_notebook_mode(data_dir, output_root, True) == 0
        mock_deps["render"].assert_not_called()

    def test_run_notebook_mode_success(self, tmp_path, mock_deps):
        nb = NotebookInfo(
            uuid="123",
            visible_name="My Note",
            file_type="notebook",
            page_count=1
        )
        mock_deps["list"].return_value = [nb]
        
        # Mock render to return a page path
        page_path = tmp_path / "page.png"
        page_path.touch()
        mock_deps["render"].return_value = [page_path]
        
        data_dir = tmp_path / "data"
        output_root = tmp_path / "output"
        
        assert _run_notebook_mode(data_dir, output_root, True) == 0
        
        mock_deps["ocr"].assert_called()
        mock_deps["layout"].assert_called()
        
        # Verify output dir created
        assert (output_root / "My_Note").is_dir()

    def test_run_camera_mode_ocr_failure(self, tmp_path, mock_deps):
        # Simulate OCR failure but fallback to empty list
        mock_deps["ocr"].side_effect = Exception("OCR Failed")
        
        data_dir = tmp_path / "data"
        output_root = tmp_path / "output"
        proj_dir = data_dir / "camera" / "proj1"
        proj_dir.mkdir(parents=True)
        (proj_dir / "img1.png").touch()
        
        assert _run_camera_mode(data_dir, output_root, "proj1", True) == 0
        
        # If all OCR fails and returns empty, layout should be skipped or handle empty
        # In implementation: if not all_ocr: return 0
        # Here we append [] on exception. So all_ocr = [[]]
        # render_ocr_to_html_multi called with [[]]
        mock_deps["layout"].assert_called()

    def test_run_notebook_mode_render_fail(self, tmp_path, mock_deps):
        nb = NotebookInfo(uuid="123", visible_name="Note", file_type="notebook", page_count=0)
        mock_deps["list"].return_value = [nb]
        mock_deps["render"].return_value = [] # Render returns no pages
        
        data_dir = tmp_path / "data"
        output_root = tmp_path / "output"
        
        assert _run_notebook_mode(data_dir, output_root, True) == 0
        mock_deps["ocr"].assert_not_called()
