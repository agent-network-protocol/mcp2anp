"""简化的数据模型定义。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigMixin:
    """Pydantic 配置 mixin。"""

    model_config = ConfigDict(populate_by_name=True)


class SetAuthRequest(ConfigMixin, BaseModel):
    """setAuth 工具请求模型。"""

    did_document_path: str = Field(
        ...,
        alias="didDocumentPath",
        description="DID 文档文件路径",
    )
    did_private_key_path: str = Field(
        ...,
        alias="didPrivateKeyPath",
        description="DID 私钥文件路径",
    )


class FetchDocRequest(ConfigMixin, BaseModel):
    """fetchDoc 工具请求模型。"""

    url: str = Field(..., description="要获取的 URL")


class InvokeOpenRPCRequest(ConfigMixin, BaseModel):
    """invokeOpenRPC 工具请求模型。"""

    endpoint: str = Field(..., description="OpenRPC 端点 URL")
    method: str = Field(..., description="要调用的方法名")
    params: dict[str, Any] | list[Any] | None = Field(
        None,
        description="方法参数",
    )
    id: str | None = Field(None, description="请求 ID")
