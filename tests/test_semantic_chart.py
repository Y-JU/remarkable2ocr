
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.layout.semantic_chart import semantic_parse

class TestSemanticChart(unittest.TestCase):

    @patch("src.layout.semantic_chart.OpenAI")
    @patch("src.layout.semantic_chart.get_ocr_api_key")
    @patch("src.layout.semantic_chart.get_ocr_model_name")
    @patch("src.layout.semantic_chart.get_ocr_base_url")
    @patch("src.layout.semantic_chart.load_env")
    def test_semantic_parse_success(self, mock_load_env, mock_get_base, mock_get_model, mock_get_key, mock_openai):
        # Setup mocks
        mock_get_key.return_value = "fake-key"
        mock_get_model.return_value = "gpt-4o"
        mock_get_base.return_value = None
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock LLM response
        expected_chart = {
            "outline": [{"level": 1, "text": "Main", "id": "o1"}],
            "containers": [{"type": "rectangle", "id": "c1", "label": "Box"}],
            "arrows": [{"from_id": "o1", "to_id": "c1", "style": "solid"}],
            "lists": [{"type": "bullet", "items": [{"text": "Item 1"}]}]
        }
        
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = f"```json\n{json.dumps(expected_chart)}\n```"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        # Input OCR lines
        ocr_lines = [
            {"text": "Main", "y_ratio": 0.1, "x_ratio": 0.1},
            {"text": "Box content", "y_ratio": 0.5, "x_ratio": 0.5}
        ]

        # Call function
        result = semantic_parse(ocr_lines)

        # Assertions
        self.assertEqual(result["outline"][0]["text"], "Main")
        self.assertEqual(len(result["containers"]), 1)
        self.assertEqual(len(result["arrows"]), 1)
        
        # Verify API call
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        self.assertIn("messages", call_args.kwargs)
        self.assertIn("Main", call_args.kwargs["messages"][0]["content"][0]["text"])

    @patch("src.layout.semantic_chart.OpenAI")
    @patch("src.layout.semantic_chart.get_ocr_api_key")
    def test_semantic_parse_invalid_json(self, mock_get_key, mock_openai):
        mock_get_key.return_value = "key"
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Not JSON"))]
        mock_client.chat.completions.create.return_value = mock_response

        result = semantic_parse([{"text": "foo"}])
        
        # Should return empty structure on failure
        self.assertEqual(result["outline"], [])
        self.assertEqual(result["containers"], [])

    @patch("src.layout.semantic_chart.OpenAI", None)
    @patch("src.layout.semantic_chart.get_ocr_api_key")
    def test_semantic_parse_missing_openai(self, mock_get_key):
        mock_get_key.return_value = "key"
        with self.assertRaises(ImportError):
            semantic_parse([{"text": "foo"}])

if __name__ == "__main__":
    unittest.main()
