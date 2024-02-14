"""[早柚协议](https://docs.sayu-bot.com/CodeAdapter/Protocol.html)客户端实现。"""
from __future__ import annotations

import asyncio
from asyncio import Queue
import json
from typing import Any, Callable, Coroutine

from .pack import MessageReceive, MessageSend

from loguru import logger
from nonebot.compat import model_dump, type_validate_python
import websockets.client
from websockets.exceptions import ConnectionClosed, WebSocketException

background_tasks = set()


class GsClient:
    """[早柚协议](https://docs.sayu-bot.com/CodeAdapter/Protocol.html)客户端。

    通过使用 `connect()` 开启连接，`send()` 发送 `MessageReceive` 包，`close()` 关闭连接。

    Attritube:
        host (str): 早柚核心的地址
        port (int): 早柚核心的端口
        bot_id (str): 连接至早柚核心时使用的 ID
        callback (Callable[[MessageSend], Coroutine[None, None, Any]]): 消息回调函数
        is_retry (bool): 是否自动重连.
        url (str): 连接地址
    """  # noqa: E501

    def __init__(
        self,
        host: str,
        port: int,
        bot_id: str,
        callback: Callable[[MessageSend], Coroutine[None, None, Any]],
        is_retry: bool = True,
    ) -> None:
        """初始化客户端。

        Args:
            host (str): 早柚核心的地址
            port (int): 早柚核心的端口
            bot_id (str): 连接至早柚核心时使用的 ID
            callback (Callable[[MessageSend], Coroutine[None, None, Any]]): 消息回调函数
            is_retry (bool, optional): 是否自动重连. Defaults to True.
        """  # noqa: E501

        self.host = host
        self.port = port
        self.bot_id = bot_id
        self.callback = callback
        self.is_retry = is_retry
        self.url = f"ws://{host}:{port}/ws/{bot_id}"

        self._msg_list: Queue[MessageReceive] = Queue()
        self._tasks = []

        self._client: websockets.client.WebSocketClientProtocol | None = None

    async def _connect(self):
        _bot_id_print = f"<yellow>{self.bot_id}</yellow>"
        while True:
            try:
                logger.opt(colors=True).info(
                    f"[{_bot_id_print}] 尝试连接至 {self.url}"
                )
                async with websockets.client.connect(
                    self.url, max_size=2**26, open_timeout=60, ping_timeout=60
                ) as ws:
                    self._client = ws
                    logger.opt(colors=True).success(
                        f"[{_bot_id_print}] 已连接至 {self.url}"
                    )

                    try:
                        recv_task = asyncio.create_task(self._recv())
                        send_task = asyncio.create_task(self._send())
                        await asyncio.gather(recv_task, send_task)
                    except ConnectionClosed as e:
                        logger.opt(colors=True).warning(
                            f"[{_bot_id_print}] 连接已关闭: "
                            f"{e.reason} ({e.code})"
                        )
                    except Exception:
                        logger.opt(colors=True).exception(
                            f"[{_bot_id_print}] 未知错误"
                        )
            except (
                ConnectionClosed,
                WebSocketException,
                ConnectionRefusedError,
            ) as e:
                logger.opt(colors=True).warning(
                    f"[{_bot_id_print}] 连接失败: {e}"
                )
            except Exception as e:
                logger.opt(colors=True).exception(
                    f"[{_bot_id_print}] 未知错误: {e}"
                )
            finally:
                self._client = None
            if not self.is_retry:
                break
            await asyncio.sleep(5)

    async def connect(self) -> None:
        """连接至早柚核心。"""
        try:
            self._tasks.append(asyncio.create_task(self._connect()))
        except Exception as e:
            logger.opt(colors=True).exception(
                f"[<yellow>{self.bot_id}</yellow>] 启动连接失败: {e}"
            )

    async def _send(self):
        while self._client is not None and self._client.open:
            msg: MessageReceive = await self._msg_list.get()
            msg_send = model_dump(msg)
            await self._client.send(json.dumps(msg_send).encode())

    async def send(self, msg: MessageReceive) -> None:
        """发送 `MessageReceive` 包至早柚核心。"""
        await self._msg_list.put(msg)

    async def _recv(self):
        while self._client is not None and self._client.open:
            data = await self._client.recv()
            msg = type_validate_python(MessageSend, json.loads(data))
            logger.opt(colors=True).info(
                f"[<yellow>{self.bot_id}</yellow> <--] {msg.target_id} "
                f"- {msg.target_type}"
            )
            task = asyncio.create_task(self.callback(msg))
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

    async def close(self) -> None:
        """关闭连接。"""
        for task in background_tasks:
            task.cancel()
        for task in self._tasks:
            task.cancel()
        background_tasks.clear()
        self._tasks.clear()
        logger.opt(colors=True).info(
            f"[<yellow>{self.bot_id}</yellow>] 已停止连接"
        )
