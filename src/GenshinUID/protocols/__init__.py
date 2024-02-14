from __future__ import annotations

import abc
from typing import ClassVar

from ..sayu_protocol import Message, MessageReceive

from nonebot import logger
from nonebot.adapters import Bot, Event

PROTOCOLS: dict[str, type[AbstractProtocol]] = {}


class AbstractProtocol(metaclass=abc.ABCMeta):
    protocol_name: ClassVar[str]

    def __init__(self, bot: Bot):
        self.id = bot.self_id
        self.bot = bot

    def __init_subclass__(cls, /, protocol_name: str, **kwargs) -> None:
        PROTOCOLS[protocol_name] = cls
        cls.protocol_name = protocol_name
        logger.opt(colors=True).debug(
            f"注册协议: <yellow>{protocol_name}</yellow>"
        )
        return super().__init_subclass__()

    @property
    def bot_id(self) -> str:
        return self.protocol_name

    @abc.abstractmethod
    async def handle_notice(self, event: Event) -> MessageReceive | None:
        pass

    @abc.abstractmethod
    async def handle_message(self, event: Event) -> MessageReceive | None:
        raise NotImplementedError

    @abc.abstractmethod
    async def send_message(
        self,
        message: list[Message],
        target_id: str,
        target_type: str,
    ):
        raise NotImplementedError
