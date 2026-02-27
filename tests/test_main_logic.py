
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Ensure main is importable
sys.path.insert(0, str(Path.cwd()))
from main import main, _run_camera_mode, _run_notebook_mode

class TestMain(unittest.TestCase):
    @patch("main.pull_xochitl")
    @patch("main.get_data_dir")
    @patch("main.load_env")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_pull_success(self, mock_args, mock_load, mock_get_dir, mock_pull):
        mock_args.return_value = MagicMock(pull=True, camera=None, no_cache=False)
        mock_get_dir.return_value = Path("/tmp/data")
        
        # Run main
        ret = main()
        
        self.assertEqual(ret, 1)
        mock_pull.assert_called_once()

    @patch("main.pull_xochitl")
    @patch("main.get_data_dir")
    @patch("main.load_env")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_pull_failure(self, mock_args, mock_load, mock_get_dir, mock_pull):
        mock_args.return_value = MagicMock(pull=True, camera=None, no_cache=False)
        mock_pull.side_effect = RuntimeError("Connection failed")
        
        ret = main()
        
        self.assertEqual(ret, 1)

    @patch("main._run_camera_mode")
    @patch("main.get_data_dir")
    @patch("main.load_env")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_camera_mode(self, mock_args, mock_load, mock_get_dir, mock_run_cam):
        mock_args.return_value = MagicMock(pull=False, camera="myproj", no_cache=True)
        mock_get_dir.return_value = MagicMock(is_dir=lambda: True)
        mock_run_cam.return_value = 0
        
        ret = main()
        
        self.assertEqual(ret, 0)
        mock_run_cam.assert_called_once()
        args = mock_run_cam.call_args[0]
        self.assertEqual(args[2], "myproj")
        self.assertEqual(args[3], False) # use_ocr_cache is not no_cache

    @patch("main._run_notebook_mode")
    @patch("main.get_data_dir")
    @patch("main.load_env")
    @patch("argparse.ArgumentParser.parse_args")
    def test_main_notebook_mode(self, mock_args, mock_load, mock_get_dir, mock_run_nb):
        mock_args.return_value = MagicMock(pull=False, camera=None, no_cache=False)
        mock_get_dir.return_value = MagicMock(is_dir=lambda: True)
        mock_run_nb.return_value = 0
        
        ret = main()
        
        self.assertEqual(ret, 0)
        mock_run_nb.assert_called_once()
        args = mock_run_nb.call_args[0]
        self.assertEqual(args[2], True) # use_ocr_cache

if __name__ == "__main__":
    unittest.main()
