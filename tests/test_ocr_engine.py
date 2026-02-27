
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.ocr.engine import ocr_image, _heuristic_confidence

class TestOCREngine(unittest.TestCase):
    def test_heuristic_confidence(self):
        self.assertEqual(_heuristic_confidence(""), 0.0)
        self.assertEqual(_heuristic_confidence("  "), 0.0)
        self.assertGreaterEqual(_heuristic_confidence("hello"), 0.5)
        self.assertGreaterEqual(_heuristic_confidence("123"), 0.6)
        self.assertGreaterEqual(_heuristic_confidence("->"), 0.6)

    @patch("src.ocr.engine.OpenAI")
    @patch("src.ocr.engine.get_ocr_api_key")
    @patch("src.ocr.engine.get_ocr_model_name")
    @patch("pathlib.Path.is_file")
    @patch("pathlib.Path.read_bytes")
    @patch("builtins.open")
    def test_ocr_image_api_call(self, mock_open, mock_read_bytes, mock_is_file, mock_get_model, mock_get_key, mock_openai):
        # Setup mocks
        mock_get_key.return_value = "fake-key"
        mock_get_model.return_value = "gpt-4o"
        mock_is_file.return_value = True
        
        # Mock file reading for base64
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake-image-data"
        mock_open.return_value.__enter__.return_value = mock_file

        # Mock OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        
        # Mock JSON response
        ocr_result = [
            {"text": "Hello", "y_ratio": 0.1, "x_ratio": 0.1},
            {"text": "World", "y_ratio": 0.2, "x_ratio": 0.1}
        ]
        mock_message.content = json.dumps(ocr_result)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # Run OCR
        with patch("src.ocr.engine.load_env"):
            # Use a temporary directory for cache
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                result = ocr_image(
                    "dummy.png",
                    Path(tmpdir),
                    use_cache=False
                )

        # Verify result
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "Hello")
        self.assertEqual(result[1]["text"], "World")
        
        # Verify OpenAI call
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["model"], "gpt-4o")
        messages = call_args.kwargs["messages"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        
    @patch("src.ocr.engine.OpenAI")
    def test_ocr_image_json_markdown_parsing(self, mock_openai):
        # Test parsing when response is wrapped in ```json ... ```
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        
        ocr_result = [{"text": "Markdown", "y_ratio": 0.5, "x_ratio": 0.5}]
        mock_message.content = f"```json\n{json.dumps(ocr_result)}\n```"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        
        from src.ocr.engine import _image_to_structured_ocr_impl
        
        with patch("builtins.open"), patch("src.ocr.engine._encode_image", return_value="base64"):
            result = _image_to_structured_ocr_impl(
                Path("dummy.png"),
                api_key="key",
                model_name="gpt-4o"
            )
            
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Markdown")

    @patch("src.ocr.engine.OpenAI")
    def test_ocr_image_invalid_json(self, mock_openai):
        # Test fallback to plain text lines when JSON is invalid
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Line 1\nLine 2"))]
        mock_client.chat.completions.create.return_value = mock_response
        
        from src.ocr.engine import _image_to_structured_ocr_impl
        
        with patch("builtins.open"), patch("src.ocr.engine._encode_image", return_value="base64"):
            result = _image_to_structured_ocr_impl(
                Path("dummy.png"),
                api_key="key"
            )
            
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["text"], "Line 1")
        self.assertEqual(result[1]["text"], "Line 2")
        # Check default coordinates
        self.assertAlmostEqual(result[0]["y_ratio"], 0.25) # (0+0.5)/2
        self.assertAlmostEqual(result[1]["y_ratio"], 0.75) # (1+0.5)/2

    @patch("src.ocr.engine.OpenAI", None)
    def test_missing_openai_module(self):
        from src.ocr.engine import _image_to_structured_ocr_impl
        with self.assertRaises(ImportError):
            _image_to_structured_ocr_impl(Path("dummy.png"), api_key="key")

if __name__ == "__main__":
    unittest.main()
