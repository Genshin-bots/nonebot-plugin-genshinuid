from __future__ import annotations

from pydantic import BaseModel


class Config(BaseModel):
    gsuid_core_botid: str = "NoneBot2"
    """连接至早柚核心时使用的 ID"""
    gsuid_core_host: str = "localhost"
    """早柚核心的地址"""
    gsuid_core_port: int = 8765
    """早柚核心的端口"""
    gsuid_core_retry: bool = True
    """连接失败时是否重试"""
