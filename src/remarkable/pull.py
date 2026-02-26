"""
Pull xochitl data from reMarkable device via SSH + rsync.
Fails with a clear error if the device is not reachable.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from ..config import (
    get_remarkable_host,
    get_remarkable_user,
    get_remarkable_xochitl_path,
)

logger = logging.getLogger(__name__)


def pull_xochitl(data_dir: Path) -> None:
    """
    Sync xochitl from reMarkable to local data_dir using rsync over SSH.
    Raises on connection failure or non-zero rsync exit.
    """
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    host = get_remarkable_host()
    user = get_remarkable_user()
    remote_path = get_remarkable_xochitl_path()
    remote = f"{user}@{host}:{remote_path.rstrip('/')}/"
    logger.info("Pulling xochitl from %s to %s", remote, data_dir)
    try:
        subprocess.run(
            [
                "rsync",
                "-avz",
                "--progress",
                remote,
                str(data_dir) + "/",
            ],
            check=True,
            capture_output=False,
        )
        logger.info("Pull completed successfully")
    except FileNotFoundError:
        raise RuntimeError(
            "rsync not found. Install rsync and ensure it is on PATH to use --pull."
        ) from None
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Pull failed (is the reMarkable connected? SSH to {user}@{host}): {e}"
        ) from e
