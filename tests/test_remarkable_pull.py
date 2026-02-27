
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.remarkable.pull import pull_xochitl

def test_pull_xochitl_success(tmp_path):
    with patch("src.remarkable.pull.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        
        data_dir = tmp_path / "data"
        pull_xochitl(data_dir)
        
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert cmd[0] == "rsync"
        assert str(data_dir) + "/" in cmd

def test_pull_xochitl_rsync_not_found(tmp_path):
    with patch("src.remarkable.pull.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="rsync not found"):
            pull_xochitl(tmp_path)

def test_pull_xochitl_failed_process(tmp_path):
    with patch("src.remarkable.pull.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["rsync"])):
        with pytest.raises(RuntimeError, match="Pull failed"):
            pull_xochitl(tmp_path)
