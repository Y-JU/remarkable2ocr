
import pytest
import logging
import argparse
from unittest.mock import patch, MagicMock
from pathlib import Path
from main import (
    main, 
    _safe_notebook_name, 
    _run_camera_mode, 
    _run_notebook_mode
)
from src.remarkable.parse import NotebookInfo, PageInfo

def test_safe_notebook_name():
    assert _safe_notebook_name("My Notebook") == "My_Notebook"
    assert _safe_notebook_name("My/Notebook") == "MyNotebook"
    assert _safe_notebook_name("") == "unnamed"
    assert _safe_notebook_name("   ") == "unnamed"
    assert _safe_notebook_name("A" * 300) == "A" * 200

@patch("main.pull_xochitl")
@patch("main.get_data_dir")
@patch("argparse.ArgumentParser.parse_args")
def test_main_pull_failure(mock_args, mock_get_data, mock_pull, caplog):
    mock_args.return_value = argparse.Namespace(
        pull=True, 
        no_cache=False, 
        camera=None
    )
    mock_pull.side_effect = Exception("Pull failed")
    
    assert main() == 1
    assert "Pull failed" in caplog.text

@patch("main._run_camera_mode")
@patch("main.get_data_dir")
@patch("argparse.ArgumentParser.parse_args")
def test_main_camera_mode(mock_args, mock_get_data, mock_camera):
    mock_args.return_value = argparse.Namespace(
        pull=False, 
        no_cache=False, 
        camera="myproject",
        xmind=True
    )
    mock_camera.return_value = 0
    
    assert main() == 0
    mock_camera.assert_called_once()

@patch("main.list_notebooks")
@patch("main.render_notebook_pages")
@patch("main.ocr_image")
@patch("main.render_ocr_to_html_multi")
@patch("main.render_ocr_overlay")
def test_run_notebook_mode_full_flow(
    mock_overlay,
    mock_render_html, 
    mock_ocr, 
    mock_render_pages, 
    mock_list, 
    tmp_path, 
    caplog
):
    caplog.set_level(logging.INFO)
    # Setup
    data_dir = tmp_path / "data"
    output_root = tmp_path / "output"
    
    # Mock notebook
    page = MagicMock(spec=PageInfo)
    page.index = 0
    nb = MagicMock(spec=NotebookInfo)
    nb.path = data_dir / "nb1"
    nb.visible_name = "My Notebook"
    nb.pages = [page]
    mock_list.return_value = [nb]
    
    # Mock render pages
    page_img = output_root / "My_Notebook" / "pages" / "page_0.png"
    page_img.parent.mkdir(parents=True, exist_ok=True)
    page_img.touch()
    mock_render_pages.return_value = [page_img]
    
    # Mock OCR
    mock_ocr.return_value = [{"text": "Hello", "box": [0,0,10,10]}]
    
    # Run
    ret = _run_notebook_mode(data_dir, output_root, use_ocr_cache=True)
    
    assert ret == 0
    assert "Notebook 1/1: My Notebook" in caplog.text
    mock_render_html.assert_called_once()
    mock_overlay.assert_called_once()


@patch("main.list_notebooks")
@patch("main.render_notebook_pages")
@patch("main.ocr_image")
def test_run_notebook_mode_ocr_fail(mock_ocr, mock_render, mock_list, tmp_path, caplog):
    # Setup
    nb = MagicMock(visible_name="OCR Fail NB")
    mock_list.return_value = [nb]
    mock_render.return_value = [Path("page_0.png")]
    
    # OCR raises exception
    mock_ocr.side_effect = Exception("API Error")
    
    _run_notebook_mode(tmp_path, tmp_path, True)
    
    # Should catch and log warning, maybe try cache
    assert "OCR page_0 failed: API Error" in caplog.text

@patch("main.list_notebooks")
@patch("main.render_notebook_pages")
@patch("main.ocr_image")
@patch("main.render_ocr_overlay")
def test_run_notebook_mode_overlay_fail(
    mock_overlay, 
    mock_ocr, 
    mock_render, 
    mock_list, 
    tmp_path, 
    caplog
):
    nb = MagicMock(visible_name="Overlay Fail NB")
    mock_list.return_value = [nb]
    mock_render.return_value = [Path("page_0.png")]
    mock_ocr.return_value = [{"text": "hi"}]
    
    mock_overlay.side_effect = Exception("Overlay error")
    
    _run_notebook_mode(tmp_path, tmp_path, True)
    
    assert "Failed to write ocr_overlay_0.png: Overlay error" in caplog.text
