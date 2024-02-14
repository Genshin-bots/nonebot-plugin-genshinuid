from __future__ import annotations

from .protocols import AbstractProtocol
from .sayu_protocol import GsClient, MessageReceive, MessageSend

from nonebot import logger

_client: GsClient | None = None
active_protocols: dict[str, AbstractProtocol] = {}
CAST_MAP = {"qqguild": "qq", "qqgroup": "qq"}


class ClientNotConnected(Exception):
    pass


async def start_client(
    host: str, port: int, bot_id: str, is_retry: bool = True
):
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.close()
    _client = GsClient(host, port, bot_id, call_bot, is_retry=is_retry)
    await _client.connect()


async def call_bot(msg: MessageSend):
    assert _client is not None
    bot_id = CAST_MAP.get(msg.bot_id, msg.bot_id)
    bot_protocol_id = f"{bot_id}--{msg.bot_self_id}"
    protocol = active_protocols.get(bot_protocol_id)
    if protocol is None:
        if bot_id == _client.bot_id:
            if msg.content:
                _data = msg.content[0]
                if _data.type and _data.type.startswith("log"):
                    _type = _data.type.split("_")[-1].lower()
                    getattr(logger, _type)(_data.data)
        else:
            logger.warning(f"[GSUID] 机器人 {bot_protocol_id} 未找到")
        return
    if msg.content is None or msg.target_id is None or msg.target_type is None:
        return
    await protocol.send_message(msg.content, msg.target_id, msg.target_type)


async def stop_client():
    global _client  # noqa: PLW0603
    if _client is not None:
        await _client.close()
        _client = None


async def send_message(msg: MessageReceive):
    if _client is None:
        logger.warning("[GSUID] 客户端已关闭")
        raise ClientNotConnected
    await _client.send(msg)
