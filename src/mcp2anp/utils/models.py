"""Data models for ANP integration."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ANPError(BaseModel):
    """ANP error response model."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    raw: Optional[Dict[str, Any]] = Field(None, description="Raw error data")


class ANPResponse(BaseModel):
    """Standard ANP response model."""

    ok: bool = Field(..., description="Success indicator")
    error: Optional[ANPError] = Field(None, description="Error details if ok=False")


class FetchDocResponse(ANPResponse):
    """Response model for fetchDoc tool."""

    content_type: Optional[str] = Field(None, description="Content type")
    text: Optional[str] = Field(None, description="Raw text content")
    json: Optional[Dict[str, Any]] = Field(None, description="Parsed JSON content")
    links: Optional[List[Dict[str, str]]] = Field(
        None, description="Extracted links to follow"
    )


class InvokeOpenRPCResponse(ANPResponse):
    """Response model for invokeOpenRPC tool."""

    result: Optional[Any] = Field(None, description="RPC result")
    raw: Optional[Dict[str, Any]] = Field(None, description="Raw JSON-RPC response")


class SetAuthRequest(BaseModel):
    """Request model for setAuth tool."""

    did_document_path: str = Field(..., alias="didDocumentPath", description="Path to DID document")
    did_private_key_path: str = Field(..., alias="didPrivateKeyPath", description="Path to DID private key")


class FetchDocRequest(BaseModel):
    """Request model for fetchDoc tool."""

    url: str = Field(..., description="URL to fetch")


class InvokeOpenRPCRequest(BaseModel):
    """Request model for invokeOpenRPC tool."""

    endpoint: str = Field(..., description="OpenRPC endpoint URL")
    method: str = Field(..., description="RPC method name")
    params: Dict[str, Any] = Field(default_factory=dict, description="Method parameters")
    id: Optional[str] = Field(None, description="Optional request ID")


class LinkInfo(BaseModel):
    """Information about a link extracted from ANP documents."""

    rel: str = Field(..., description="Link relationship")
    url: str = Field(..., description="Link URL")
    protocol: Optional[str] = Field(None, description="Protocol type")
    title: Optional[str] = Field(None, description="Link title")


class AgentDescription(BaseModel):
    """ANP Agent Description model."""

    protocol_type: str = Field(..., description="Protocol type (should be 'ANP')")
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    interfaces: List[Dict[str, Any]] = Field(
        default_factory=list, description="Available interfaces"
    )
    informations: List[Dict[str, Any]] = Field(
        default_factory=list, description="Information resources"
    )