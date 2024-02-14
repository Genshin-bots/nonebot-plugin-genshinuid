from __future__ import annotations

import importlib
from pathlib import Path
from pkgutil import iter_modules

from .client import (
    ClientNotConnected,
    active_protocols,
    send_message,
    start_client,
    stop_client,
)
from .config import Config
from .protocols import PROTOCOLS

from nonebot import get_driver, get_plugin_config, on, on_message, on_notice
from nonebot.adapters import Bot, Event
from nonebot.matcher import Matcher
from nonebot.plugin import PluginMetadata
from nonebot.typing import T_State

__plugin_meta__ = PluginMetadata(
    name="GenshinUID",
    description="支持大部分适配器的全功能NoneBot2原神插件",
    usage="{插件用法}",
    type="application",
    homepage="https://github.com/Genshin-bots/nonebot-plugin-genshinuid",
    config=Config,
    supported_adapters={
        "~onebot.v11",
        "~dodo",
        "~kaiheila",
        "~villa",
        "~telegram",
        "~discord",
        "~qq",
        "~feishu",
        "~red",
        "~ntchat",
        "~onebot.v12",
    },
)

get_message = on_message(priority=999, state={"gsuid_type": "message"})
get_notice = on_notice(priority=999, state={"gsuid_type": "notice"})
get_tn = on("inline", state={"gsuid_type": "notice"})

driver = get_driver()
config = get_plugin_config(Config)

for module_info in iter_modules([str(Path(__file__).parent / "protocols")]):
    if module_info.name.startswith("_"):
        continue
    module_name = f"GenshinUID.protocols.{module_info.name}"
    importlib.import_module(module_name)

ADAPTER_TO_PROTOCOL = {
    "OneBot V11": "onebot",
    "OneBot V12": "onebot_v12",
    "DoDo": "dodo",
    "Kaiheila": "kaiheila",
    "Villa": "villa",
    "Telegram": "telegram",
    "Discord": "discord",
    "Feishu": "feishu",
    "RedProtocol": "onebot:red",
    "ntchat": "ntchat",
    "QQ": "qq",
}


@driver.on_startup
async def _():
    await start_client(
        config.gsuid_core_host,
        config.gsuid_core_port,
        config.gsuid_core_botid,
        config.gsuid_core_retry,
    )


@driver.on_shutdown
async def _():
    await stop_client()


@driver.on_bot_connect
async def _(bot: Bot):
    protocol_name = ADAPTER_TO_PROTOCOL[bot.adapter.get_name()]
    protocol = PROTOCOLS[protocol_name](bot)
    active_protocols[f"{protocol_name}--{bot.self_id}"] = protocol


@driver.on_bot_disconnect
async def _(bot: Bot):
    active_protocols.pop(
        f"{ADAPTER_TO_PROTOCOL[bot.adapter.get_name()]}--{bot.self_id}", None
    )


@get_tn.handle()
@get_notice.handle()
@get_message.handle()
async def handle_notice(
    bot: Bot, event: Event, matcher: Matcher, state: T_State
):
    protocol = active_protocols.get(
        f"{ADAPTER_TO_PROTOCOL[bot.adapter.get_name()]}--{bot.self_id}"
    )
    if protocol is None:
        await matcher.finish()
    message_receive = await getattr(protocol, f"handle_{state['gsuid_type']}")(
        event
    )
    if message_receive is None:
        await matcher.finish()
    try:
        await send_message(message_receive)
    except ClientNotConnected:
        await start_client(
            config.gsuid_core_host,
            config.gsuid_core_port,
            config.gsuid_core_botid,
            config.gsuid_core_retry,
        )
    await matcher.finish()
