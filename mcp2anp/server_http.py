from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import click
import httpx
import structlog
import uvicorn
from anp.anp_crawler.anp_crawler import ANPCrawler
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from pydantic_settings import BaseSettings

from .core.handlers import ANPHandler

# --------------------------------------------------------------------------- #
# Settings & Logging
# --------------------------------------------------------------------------- #


class Settings(BaseSettings):
    # HTTP server
    host: str = "0.0.0.0"
    port: int = 9881
    log_level: str = "INFO"

    # Remote auth service
    auth_base_url: str = "https://didhost.cc"
    auth_verify_path: str = "/api/v1/mcp-sk-api-keys/verify"
    api_key_header: str = "X-API-Key"
    auth_timeout_s: float = 15.0


_settings_override: dict[str, Any] = {}


def get_settings() -> Settings:
    """Return settings with CLI overrides."""
    return Settings(**_settings_override)


SENSITIVE_KEYS = {"X-API-Key", "private_pem_path", "did_doc_path"}


def _redact_map(d: dict[str, Any]) -> dict[str, Any]:
    """Redact known sensitive keys for safe logging."""
    return {k: ("***redacted***" if k in SENSITIVE_KEYS else v) for k, v in d.items()}


def setup_logging(level: str) -> None:
    """Setup structlog & std logging."""
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
    )


logger = structlog.get_logger(__name__)

# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #


class DidAuthResponse(BaseModel):
    """Remote auth response payload."""

    did: str
    did_doc_path: str
    private_pem_path: str


class SessionConfig(BaseModel):
    """Resolved session config used to init ANP crawler."""

    did_document_path: str
    private_key_path: str


class FetchDocIn(BaseModel):
    """Input model for anp.fetchDoc."""

    url: HttpUrl = Field(..., description="ANP doc url to fetch")


class InvokeOpenRPCIn(BaseModel):
    """Input model for anp.invokeOpenRPC."""

    endpoint: HttpUrl = Field(..., description="OpenRPC endpoint URL")
    method: str = Field(..., min_length=1, description="RPC method name")
    params: Any | None = Field(default=None, description="Params for the RPC method")
    request_id: str | int | None = Field(
        default=None, alias="id", description="Optional request id"
    )

    class Config:
        populate_by_name = True


class ToolError(BaseModel):
    code: str
    message: str


class ToolEnvelope(BaseModel):
    ok: bool
    data: Any | None = None
    error: ToolError | None = None


# --------------------------------------------------------------------------- #
# Lifespan: shared AsyncClient
# --------------------------------------------------------------------------- #


async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """App lifespan: create & close shared httpx AsyncClient."""
    settings = get_settings()
    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.auth_timeout_s),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    )
    logger.info("httpx client initialized")
    try:
        yield
    finally:
        await app.state.http.aclose()
        logger.info("httpx client closed")


app = FastAPI(
    title="MCP2ANP FastAPI Server",
    version="1.0.0",
    summary="Expose ANP tools via FastAPI: anp.fetchDoc & anp.invokeOpenRPC",
    description=(
        "这是一个 ANP 网络的 FastAPI 服务器包装层。"
        "你可以通过 /anp.fetchDoc 抓取文档，通过 /anp.invokeOpenRPC 调用 OpenRPC 接口。"
        "所有请求必须通过 X-API-Key 进行远程鉴权。"
    ),
    lifespan=lifespan,
)

# --------------------------------------------------------------------------- #
# Exceptions & Utilities
# --------------------------------------------------------------------------- #


class AuthFailure(HTTPException):
    """Raised when remote auth fails."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


@app.exception_handler(ValidationError)
async def on_validation_error(_: Request, exc: ValidationError):
    logger.warning("Request validation error", errors=exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ToolEnvelope(
            ok=False, error=ToolError(code="VALIDATION_ERROR", message=str(exc))
        ).model_dump(),
    )


@app.exception_handler(httpx.HTTPError)
async def on_httpx_error(_: Request, exc: httpx.HTTPError):
    logger.error("Downstream HTTP error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ToolEnvelope(
            ok=False, error=ToolError(code="UPSTREAM_HTTP_ERROR", message=str(exc))
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def on_unhandled(_: Request, exc: Exception):
    logger.error("Unhandled error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ToolEnvelope(
            ok=False,
            error=ToolError(code="INTERNAL_ERROR", message="Internal server error"),
        ).model_dump(),
    )


# --------------------------------------------------------------------------- #
# Helpers: auth retry & URL safety
# --------------------------------------------------------------------------- #


async def auth_call(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    attempts: int = 3,
) -> httpx.Response:
    """GET with exponential backoff for transient auth failures."""
    retryable = {429, 500, 502, 503, 504}
    for i in range(attempts):
        try:
            resp = await client.get(url, headers=headers)
            # retry on retryable status codes (except 401 which is hard-fail)
            if resp.status_code in retryable:
                raise httpx.HTTPStatusError(
                    "retryable status",
                    request=resp.request,
                    response=resp,
                )
            return resp
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if i == attempts - 1:
                raise
            # jittered exponential backoff: 2^i + [0,1)
            backoff = (2**i) + random.random()
            logger.warning(
                "auth call retrying", attempt=i + 1, error=str(e), backoff=backoff
            )
            await asyncio.sleep(backoff)


# --------------------------------------------------------------------------- #
# Dependencies
# --------------------------------------------------------------------------- #


async def verify_api_key(
    request: Request, settings: Settings = Depends(get_settings)
) -> SessionConfig:
    """Validate X-API-Key via remote service and return SessionConfig."""
    token = request.headers.get(settings.api_key_header, "").strip()
    if not token:
        logger.warning("Missing API key header")
        raise AuthFailure("Missing X-API-Key")

    verify_url = f"{settings.auth_base_url}{settings.auth_verify_path}"
    logger.info(
        "verifying api key",
        verify_url=verify_url,
        header=_redact_map({settings.api_key_header: "present"}),
    )

    try:
        resp = await auth_call(
            client=request.app.state.http,
            url=verify_url,
            headers={settings.api_key_header: token},
            attempts=3,
        )
        if resp.status_code == status.HTTP_401_UNAUTHORIZED:
            logger.warning("invalid api key")
            raise AuthFailure("Invalid or expired API key")

        resp.raise_for_status()
        payload = resp.json()
        auth = DidAuthResponse.model_validate(payload)

        logger.info("auth ok", did=auth.did)
        return SessionConfig(
            did_document_path=auth.did_doc_path, private_key_path=auth.private_pem_path
        )

    except httpx.HTTPStatusError as e:
        logger.error("auth service status error", status=e.response.status_code)
        raise AuthFailure("Auth service error") from e
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error("auth response parse error", error=str(e))
        raise AuthFailure("Auth response invalid") from e
    except httpx.RequestError as e:
        logger.error("auth request failed", error=str(e))
        raise AuthFailure("Auth service unreachable") from e


@dataclass
class Components:
    """Per-request initialized components."""

    anp_handler: ANPHandler
    # You can expose crawler too if you need more controls
    # anp_crawler: ANPCrawler


async def get_components(cfg: SessionConfig = Depends(verify_api_key)) -> Components:
    """Initialize ANP components; designed for quick construction per request."""
    # NOTE: ANPCrawler likely holds caches internally; enable its cache to avoid re-fetching
    crawler = ANPCrawler(
        did_document_path=cfg.did_document_path,
        private_key_path=cfg.private_key_path,
        cache_enabled=True,
    )
    handler = ANPHandler(crawler)
    return Components(anp_handler=handler)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #


@app.post(
    "/anp.fetchDoc", response_model=ToolEnvelope, summary="抓取并解析 ANP 文档"
)
async def anp_fetch_doc(
    payload: FetchDocIn, comps: Components = Depends(get_components)
) -> ToolEnvelope:
    """抓取并解析 ANP 文档，提取可跟进的链接。

    Args:
        payload: FetchDocIn
        comps: DI-provided Components

    Returns:
        ToolEnvelope with result from ANPHandler.handle_fetch_doc
    """
    logger.info("tool call", tool="anp.fetchDoc", url=str(payload.url))
    try:
        result = await comps.anp_handler.handle_fetch_doc({"url": str(payload.url)})
        return ToolEnvelope(ok=True, data=result)
    except asyncio.CancelledError:
        logger.warning("fetch cancelled")
        raise
    except Exception as e:
        logger.error("tool exec failed", tool="anp.fetchDoc", error=str(e))
        return ToolEnvelope(
            ok=False, error=ToolError(code="EXECUTION_ERROR", message=str(e))
        )


@app.post(
    "/anp.invokeOpenRPC",
    response_model=ToolEnvelope,
    summary="调用 OpenRPC 接口",
)
async def anp_invoke_openrpc(
    payload: InvokeOpenRPCIn, comps: Components = Depends(get_components)
) -> ToolEnvelope:
    """使用 JSON-RPC 2.0 协议调用 ANP OpenRPC 方法。

    Args:
        payload: InvokeOpenRPCIn
        comps: DI-provided Components

    Returns:
        ToolEnvelope with result from ANPHandler.handle_invoke_openrpc
    """
    args: dict[str, Any] = {"endpoint": str(payload.endpoint), "method": payload.method}
    if payload.params is not None:
        args["params"] = payload.params
    if payload.request_id is not None:
        args["id"] = payload.request_id

    logger.info("tool call", tool="anp.invokeOpenRPC", method=payload.method)
    try:
        result = await comps.anp_handler.handle_invoke_openrpc(args)
        return ToolEnvelope(ok=True, data=result)
    except asyncio.CancelledError:
        logger.warning("rpc cancelled")
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("tool exec failed", tool="anp.invokeOpenRPC", error=str(e))
        return ToolEnvelope(
            ok=False, error=ToolError(code="EXECUTION_ERROR", message=str(e))
        )


# --------------------------------------------------------------------------- #
# Entrypoint
# --------------------------------------------------------------------------- #


@click.command()
@click.option(
    "--host",
    default="0.0.0.0",
    help="服务器监听地址",
)
@click.option(
    "--port",
    default=9881,
    type=int,
    help="服务器监听端口",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="设置日志级别",
)
def main(host: str, port: int, log_level: str) -> None:
    """CLI entry to launch the server with configured logging."""
    _settings_override.update(host=host, port=port, log_level=log_level)
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("starting server", host=settings.host, port=settings.port)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        ws="none",
        factory=False,
    )


if __name__ == "__main__":
    main()
