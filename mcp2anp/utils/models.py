"""Data models for ANP integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigMixin:
    """Pydantic configuration mixin to enable alias population."""

    model_config = ConfigDict(populate_by_name=True)


class ANPError(ConfigMixin, BaseModel):
    """ANP error response model."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    raw: dict[str, Any] | None = Field(None, description="Raw error data")


class ANPResponse(ConfigMixin, BaseModel):
    """Standard ANP response model."""

    ok: bool = Field(..., description="Success indicator")
    error: ANPError | None = Field(None, description="Error details if ok=False")


class FetchDocResponse(ANPResponse):
    """Response model for fetchDoc tool."""

    content_type: str | None = Field(
        None,
        alias="contentType",
        description="Content type",
    )
    encoding: str | None = Field(
        None,
        alias="encoding",
        description="Encoding applied to the text field",
    )
    text: str | None = Field(
        None,
        alias="text",
        description="Raw text content or base64 for binary",
    )
    json: dict[str, Any] | None = Field(
        None,
        alias="json",
        description="Parsed JSON content",
    )
    links: list[LinkInfo] | None = Field(
        None,
        alias="links",
        description="Extracted links to follow",
    )


class InvokeOpenRPCResponse(ANPResponse):
    """Response model for invokeOpenRPC tool."""

    result: Any | None = Field(
        None,
        alias="result",
        description="RPC result",
    )
    raw: dict[str, Any] | None = Field(
        None,
        alias="raw",
        description="Raw JSON-RPC response",
    )


class SetAuthRequest(ConfigMixin, BaseModel):
    """Request model for setAuth tool."""

    did_document_path: str = Field(..., alias="didDocumentPath", description="Path to DID document")
    did_private_key_path: str = Field(..., alias="didPrivateKeyPath", description="Path to DID private key")


class FetchDocRequest(ConfigMixin, BaseModel):
    """Request model for fetchDoc tool."""

    url: str = Field(..., description="URL to fetch")


class InvokeOpenRPCRequest(ConfigMixin, BaseModel):
    """Request model for invokeOpenRPC tool."""

    endpoint: str = Field(..., description="OpenRPC endpoint URL")
    method: str = Field(..., description="RPC method name")
    params: dict[str, Any] = Field(default_factory=dict, description="Method parameters")
    id: str | None = Field(None, description="Optional request ID")


class LinkInfo(ConfigMixin, BaseModel):
    """Information about a link extracted from ANP documents."""

    rel: str = Field(..., description="Link relationship")
    url: str = Field(..., description="Link URL")
    protocol: str | None = Field(None, description="Protocol type")
    title: str | None = Field(None, description="Link title")


class AgentDescription(ConfigMixin, BaseModel):
    """ANP Agent Description model."""

    protocol_type: str = Field(..., description="Protocol type (should be 'ANP')")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    interfaces: list[dict[str, Any]] = Field(
        default_factory=list, description="Available interfaces"
    )
    informations: list[dict[str, Any]] = Field(
        default_factory=list, description="Information resources"
    )
