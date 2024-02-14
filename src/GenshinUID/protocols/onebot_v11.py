from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Literal, cast
from typing_extensions import override

from . import AbstractProtocol
from ..sayu_protocol import Message, MessageReceive
from ..utils import command_start, del_file, store_file

from nonebot.compat import model_dump
from nonebot.permission import SUPERUSER
from pydantic import BaseModel

if TYPE_CHECKING:
    from nonebot.adapters.onebot.v11 import (
        Bot,
        MessageEvent,
        MessageSegment as OBMS,
        NoticeEvent,
    )

try:
    from nonebot.adapters.onebot.v11 import Adapter, NoticeEvent

    class File(BaseModel):
        name: str
        size: int
        url: str

        class Config:
            extra = "allow"

    class OfflineFileNoticeEvent(NoticeEvent):
        """接收到离线文件 (go-cqhttp/Shamrock)"""

        notice_type: Literal["offline_file"]
        user_id: int
        file: File

        @override
        def get_user_id(self) -> str:
            return str(self.user_id)

        @override
        def get_session_id(self) -> str:
            return str(self.user_id)

    Adapter.add_custom_model(OfflineFileNoticeEvent)
except ImportError:
    pass


class UploadFile(BaseModel):
    path: Path
    name: str


class OneBotV11Protocol(AbstractProtocol, protocol_name="onebot"):
    def __init__(self, bot: "Bot"):
        super().__init__(bot)

    async def handle_notice(self, event: "NoticeEvent"):
        from nonebot.adapters.onebot.v11 import GroupUploadNoticeEvent

        pm = 1 if await SUPERUSER(self.bot, event) else 6

        if isinstance(event, GroupUploadNoticeEvent):
            group_id = str(event.group_id)
            user_type = "group"
        elif isinstance(event, OfflineFileNoticeEvent):
            group_id = None
            user_type = "direct"
        else:
            return None
        message = [Message("file", f"{event.file.name}|{event.file.url}")]  # type: ignore
        return MessageReceive(
            bot_id=self.bot_id,
            bot_self_id=self.id,
            user_type=user_type,
            group_id=group_id,
            user_id=event.get_user_id(),
            sender={},
            content=message,
            msg_id="",
            user_pm=pm,
        )

    async def handle_message(self, event: "MessageEvent"):
        from nonebot.adapters.onebot.v11.event import (
            GroupMessageEvent,
            PrivateMessageEvent,
        )

        if not isinstance(event, (GroupMessageEvent, PrivateMessageEvent)):
            return None
        pm = 6
        original_message = event.original_message
        msg_id = str(event.message_id)
        user_id = event.get_user_id()
        if event.sender.role == "owner":
            pm = 2
        elif event.sender.role == "admin":
            pm = 3

        sender = model_dump(event.sender)
        sender["avatar"] = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"

        if isinstance(event, GroupMessageEvent):
            user_type = "group"
            group_id = str(event.group_id)
        else:
            user_type = "direct"
            group_id = None

        message: list[Message] = []
        for i, segment in enumerate(original_message):
            msg = self._convert_ob_message(segment, i)
            if msg:
                message.append(msg)

        return MessageReceive(
            bot_id=self.bot_id,
            bot_self_id=self.id,
            user_type=user_type,
            group_id=group_id,
            user_id=user_id,
            sender=sender,
            content=message,
            msg_id=msg_id if msg_id else "",
            user_pm=pm,
        )

    async def send_message(
        self,
        message: list[Message],
        target_id: str,
        target_type: str,
    ):
        from nonebot.adapters.onebot.v11 import (
            Message as OBMessage,
            MessageSegment as OBMS,
        )

        _target_id = int(target_id)

        async def _send_node(messages: list[dict[str, Any]]):
            if target_type == "group":
                await self.bot.call_api(
                    "send_group_forward_msg",
                    group_id=_target_id,
                    messages=messages,
                )
            else:
                await self.bot.call_api(
                    "send_private_forward_msg",
                    user_id=_target_id,
                    messages=messages,
                )

        async def send_file(file: UploadFile):
            path = file.path
            file_name = file.name
            if target_type == "group":
                await self.bot.call_api(
                    "upload_group_file",
                    file=str(path.absolute()),
                    name=file_name,
                    group_id=_target_id,
                )
            else:
                await self.bot.call_api(
                    "upload_private_file",
                    file=str(path.absolute()),
                    name=file_name,
                    user_id=_target_id,
                )
            del_file(path)

        at_list = []
        content = OBMessage()
        for i in message:
            converted_msg = self._convert_sayu_message(i)
            if isinstance(converted_msg, list):
                await _send_node(
                    [
                        self._to_json(msg, "小助手", 2854196310)
                        for msg in converted_msg
                    ]
                )
                return
            if isinstance(converted_msg, UploadFile):
                await send_file(converted_msg)
                return
            if isinstance(converted_msg, OBMS):
                if converted_msg.type == "at":
                    at_list.append(converted_msg)
                    continue
                content.append(converted_msg)

        for i in at_list:
            content.append(i)

        if target_type == "group":
            await self.bot.call_api(
                "send_group_msg",
                group_id=target_id,
                message=content,
            )
        else:
            await self.bot.call_api(
                "send_private_msg",
                user_id=_target_id,
                message=content,
            )

    def _convert_ob_message(
        self, segment: "OBMS", index: int
    ) -> Message | None:
        msg = None
        if segment.is_text():
            data: str = segment.data["text"]

            if index in (0, 1):
                for word in command_start:
                    _data = data.strip()
                    if _data.startswith(word):
                        data = _data[len(word) :]
                        break
            msg = Message(type="text", data=data)
        elif segment.type == "image":
            msg = Message(type="image", data=segment.data["url"])
        elif segment.type == "at":
            msg = Message(type="at", data=segment.data["qq"])
        elif segment.type == "reply":
            msg = Message(type="reply", data=segment.data["id"])
        return msg

    def _convert_sayu_message(
        self, segment: Message
    ) -> "OBMS | UploadFile | list[OBMS] | None":
        from nonebot.adapters.onebot.v11 import MessageSegment as OBMS

        msg = None
        if segment.type == "text":
            msg = OBMS.text(cast(str, segment.data))
        elif segment.type == "image":
            msg = OBMS.image(cast(str, segment.data).replace("link://", ""))
        elif segment.type == "at":
            msg = OBMS.at(cast(str, segment.data))
        elif segment.type == "file":
            file = cast(str, segment.data)
            file_name, file_content = file.split("|")
            path = Path(__file__).resolve().parent / file_name
            store_file(path, file_content)
            msg = UploadFile(path=path, name=file_name)
        elif segment.type == "node":
            msgs = []
            for node in cast(List[Message], segment.data):
                msg = self._convert_sayu_message(node)
                if isinstance(msg, OBMS):
                    msgs.append(msg)
            return msgs
        return msg

    def _to_json(self, msg: OBMS, name: str, uin: int):
        return {
            "type": "node",
            "data": {"name": name, "uin": uin, "content": msg},
        }
