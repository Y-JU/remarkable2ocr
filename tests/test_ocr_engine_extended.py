
import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import json
from src.ocr.engine import (
    _heuristic_confidence, 
    ocr_image, 
    _image_to_structured_ocr_impl
)

class TestOCREngineExtended:
    def test_heuristic_confidence(self):
        assert _heuristic_confidence("") == 0.0
        assert _heuristic_confidence("   ") == 0.0
        
        # Base score 0.5
        # len >= 2: +0.2 -> 0.7
        assert _heuristic_confidence("Hi") == 0.7
        
        # digits: +0.1
        # len>=2 (0.7) + digit (0.1) -> 0.8
        # Use approx for float comparison
        assert _heuristic_confidence("A1") == pytest.approx(0.8)
        
        # symbols: +0.1
        # len>=2 (0.7) + symbol (0.1) -> 0.8
        assert _heuristic_confidence("->") == pytest.approx(0.8)
        
        # Max cap
        # The function logic is: 0.5 + 0.2(len) + 0.1(digit) + 0.1(symbol) = 0.9 max actually
        # unless I misread the code.
        # Code:
        # score = 0.5
        # if len(t) >= 2: score += 0.2  (0.7)
        # if any(c.isdigit()...): score += 0.1 (0.8)
        # if any(c in t ...): score += 0.1 (0.9)
        # return min(1.0, score)
        # So max possible is 0.9.
        assert _heuristic_confidence("A really long string with 123 numbers and -> arrows") == pytest.approx(0.9)

    def test_ocr_image_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ocr_image(tmp_path / "missing.png", tmp_path / "cache")

    def test_ocr_image_cache_hit(self, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.touch()
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        
        # Create cache file
        # Key will be generated from path hash if not provided
        # Let's provide explicit key
        cache_key = "mykey"
        cache_file = cache_dir / f"{cache_key}.json"
        
        cache_data = [
            {"text": "Cached", "y_ratio": 0.1, "x_ratio": 0.2, "confidence": 0.9, "links": [1], "shape": "box", "color": "red"}
        ]
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")
        
        result = ocr_image(img_path, cache_dir, cache_key=cache_key, use_cache=True)
        assert len(result) == 1
        assert result[0]["text"] == "Cached"
        assert result[0]["confidence"] == 0.9
        assert result[0]["links"] == [1]
        assert result[0]["shape"] == "box"
        assert result[0]["color"] == "red"

    def test_ocr_image_cache_corrupt(self, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.touch()
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cache_key = "corrupt"
        cache_file = cache_dir / f"{cache_key}.json"
        cache_file.write_text("invalid json", encoding="utf-8")
        
        # Should fallback to API
        with patch("src.ocr.engine._image_to_structured_ocr_impl") as mock_impl:
            mock_impl.return_value = []
            with patch("src.ocr.engine.get_ocr_api_key", return_value="key"):
                 ocr_image(img_path, cache_dir, cache_key=cache_key, use_cache=True)
                 mock_impl.assert_called()

    def test_ocr_image_no_api_key(self, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.touch()
        
        with patch("src.ocr.engine.get_ocr_api_key", return_value=None):
             with pytest.raises(ValueError, match="Set OCR_API_KEY"):
                 ocr_image(img_path, tmp_path / "cache", use_cache=False)

    def test_impl_openai_missing(self, tmp_path):
        # Mock OpenAI import missing
        with patch("src.ocr.engine.OpenAI", None):
            with pytest.raises(ImportError, match="pip install openai"):
                _image_to_structured_ocr_impl(tmp_path / "img.png", api_key="key")

    def test_impl_json_parsing_logic(self, tmp_path):
        # Test the parsing logic of OpenAI response
        img_path = tmp_path / "img.png"
        img_path.write_bytes(b"fake image data")
        
        mock_client = MagicMock()
        mock_completion = MagicMock()
        
        # Case 1: Markdown JSON block
        mock_completion.choices[0].message.content = '```json\n[{"text": "A"}]\n```'
        mock_client.chat.completions.create.return_value = mock_completion
        
        with patch("src.ocr.engine.OpenAI", return_value=mock_client):
             res = _image_to_structured_ocr_impl(img_path, api_key="key")
             assert res[0]["text"] == "A"
             
        # Case 2: Plain JSON array
        mock_completion.choices[0].message.content = '[{"text": "B"}]'
        with patch("src.ocr.engine.OpenAI", return_value=mock_client):
             res = _image_to_structured_ocr_impl(img_path, api_key="key")
             assert res[0]["text"] == "B"
             
        # Case 3: Malformed JSON -> Text lines fallback
        mock_completion.choices[0].message.content = 'Just some text\nLine 2'
        with patch("src.ocr.engine.OpenAI", return_value=mock_client):
             res = _image_to_structured_ocr_impl(img_path, api_key="key")
             assert len(res) == 2
             assert res[0]["text"] == "Just some text"
             assert res[1]["text"] == "Line 2"
             
    def test_impl_api_error(self, tmp_path):
        img_path = tmp_path / "img.png"
        img_path.write_bytes(b"data")
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        with patch("src.ocr.engine.OpenAI", return_value=mock_client):
             with pytest.raises(RuntimeError, match="OpenAI SDK request failed"):
                 _image_to_structured_ocr_impl(img_path, api_key="key")

    def test_impl_advanced_fields(self, tmp_path):
        # Test confidence strings, links validation, shape, color
        img_path = tmp_path / "img.png"
        img_path.write_bytes(b"data")
        
        content = json.dumps([
            {
                "text": "High Conf", 
                "confidence": "High", 
                "links": [0, 99], # 0 valid (self loop ok?), 99 invalid (out of bounds)
                "shape": "box",
                "color": "blue"
            },
            {
                "text": "Low Conf",
                "confidence": 0.1,
                "shape": "invalid_shape"
            }
        ])
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value.choices[0].message.content = content
        
        with patch("src.ocr.engine.OpenAI", return_value=mock_client):
             res = _image_to_structured_ocr_impl(img_path, api_key="key")
             
             assert res[0]["confidence"] == "high"
             assert res[0]["links"] == [0] # 99 filtered out
             assert res[0]["shape"] == "box"
             assert res[0]["color"] == "blue"
             
             assert res[1]["confidence"] == 0.1
             assert "shape" not in res[1]
