
import pytest
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.layout.semantic_chart import semantic_parse, _encode_image

def test_encode_image(tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"fake image data")
    # Base64 of "fake image data" is "ZmFrZSBpbWFnZSBkYXRh"
    assert _encode_image(img) == "ZmFrZSBpbWFnZSBkYXRh"

@patch("src.layout.semantic_chart.OpenAI")
@patch("src.layout.semantic_chart.load_env")
@patch("src.layout.semantic_chart.get_ocr_api_key", return_value="fake-key")
def test_semantic_parse_with_image(mock_key, mock_load, mock_openai, tmp_path):
    # Setup
    img = tmp_path / "test.png"
    img.write_bytes(b"data")
    
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = '{"chart": []}'
    mock_client.chat.completions.create.return_value = mock_resp
    
    ocr_lines = [{"text": "Node 1", "y_ratio": 0.1, "x_ratio": 0.1}]
    
    # Run
    semantic_parse(ocr_lines, image_path=img)
    
    # Verify image was included
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    content = messages[0]["content"] # list of dicts
    
    has_image = False
    for part in content:
        if isinstance(part, dict) and part.get("type") == "image_url":
            has_image = True
            assert part["image_url"]["url"].startswith("data:image/png;base64,")
    
    assert has_image

@patch("src.layout.semantic_chart.OpenAI", None)
@patch("src.layout.semantic_chart.get_ocr_api_key", return_value="fake-key")
def test_semantic_parse_no_openai_module(mock_key):
    with pytest.raises(ImportError, match="Please install openai"):
        semantic_parse([])

@patch("src.layout.semantic_chart.OpenAI")
@patch("src.layout.semantic_chart.get_ocr_api_key", return_value="fake-key")
def test_semantic_parse_api_error(mock_key, mock_openai):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API Down")
    
    with pytest.raises(RuntimeError, match="LLM did not return text"):
        semantic_parse([])
