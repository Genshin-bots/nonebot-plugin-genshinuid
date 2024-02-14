from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path

from nonebot import get_driver

driver = get_driver()

command_start = deepcopy(driver.config.command_start)
command_start.discard("")


def store_file(path: Path, file: str):
    file_content = base64.b64decode(file).decode()
    with path.open("w") as f:
        f.write(file_content)


def del_file(path: Path):
    if path.exists():
        path.unlink()
