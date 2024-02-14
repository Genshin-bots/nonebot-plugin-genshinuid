"""[早柚协议](https://docs.sayu-bot.com/CodeAdapter/Protocol.html)的 Python 实现。

为兼容 Pydantic v2，部分使用了 nonebot 的兼容代码
稍加修改可移植到其他的 Python Bot 端实现
"""  # noqa: E501
from __future__ import annotations

from .gs_client import GsClient as GsClient
from .pack import (
    Message as Message,
    MessageReceive as MessageReceive,
    MessageSend as MessageSend,
)
