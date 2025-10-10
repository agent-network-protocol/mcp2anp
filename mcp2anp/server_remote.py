"""远程 MCP 服务器实现（独立 fastmcp + Streamable HTTP）。"""

import json
from collections.abc import Callable
from typing import Any

import click
import httpx
import structlog
import uvicorn
from agent_connect.anp_crawler.anp_crawler import ANPCrawler
from fastmcp import Context, FastMCP
from fastmcp.server.dependencies import (
    get_http_headers,  # 读取请求头
)
from pydantic import BaseModel, ValidationError

from .core.handlers import ANPHandler
from .utils import setup_logging

logger = structlog.get_logger(__name__)

# 远程认证服务配置
# TODO: 后面改为 didhost.cc
AUTH_HOST = "127.0.0.1"
AUTH_PORT = 9866
AUTH_VERIFY_PATH = "/api/v1/mcp-sk-api-keys/verify"

# 存放本请求期（一次工具调用）所需的组件与配置
STATE_KEY = "mcp2anp"


class SessionConfig:
    """会话配置信息：存储会话所需的 DID 凭证路径。"""

    def __init__(self, did_document_path: str, private_key_path: str):
        self.did_document_path = did_document_path
        self.private_key_path = private_key_path


# 鉴权回调函数类型（接收 token 字符串，返回 SessionConfig 或 None）
AuthCallback = Callable[[str], SessionConfig | None]

# 全局鉴权回调函数
_auth_callback: AuthCallback | None = None


def set_auth_callback(callback: AuthCallback | None) -> None:
    """设置自定义鉴权回调函数。"""
    global _auth_callback
    _auth_callback = callback
    logger.info("Auth callback set", has_callback=callback is not None)


class DidAuthResponse(BaseModel):
    """远程认证服务响应模型。"""

    did: str
    did_doc_path: str
    private_pem_path: str


def create_did_auth_callback(
    verify_url: str, api_key_header: str = "X-API-Key"
) -> AuthCallback:
    """创建一个通过远程 API 验证 token 并返回 DID 配置的回调函数。"""

    def did_auth_callback(token: str) -> SessionConfig | None:
        if not token:
            logger.warning("DID auth callback received an empty token.")
            return None

        headers = {api_key_header: token}
        logger.info(
            "Calling remote auth service to verify key via httpx",
            url=verify_url,
            header_name=api_key_header,
        )

        try:
            response = httpx.get(verify_url, headers=headers, timeout=15)
            response.raise_for_status()

            try:
                payload = response.json()
                auth_data = DidAuthResponse.model_validate(payload)
                logger.info("Remote auth successful", did=auth_data.did)
                return SessionConfig(
                    did_document_path=auth_data.did_doc_path,
                    private_key_path=auth_data.private_pem_path,
                )
            except (json.JSONDecodeError, ValidationError) as e:
                logger.error(
                    "Auth response parsing failed",
                    error=str(e),
                    response_data=response.text,
                )
                return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning(
                    "Remote auth failed: Invalid or missing API Key.",
                    response=e.response.text,
                )
            else:
                logger.error(
                    "Remote auth service returned an error",
                    status_code=e.response.status_code,
                    response=e.response.text,
                )
            return None
        except httpx.RequestError as e:
            logger.error("HTTP request to auth service failed", error=str(e))
            return None

    return did_auth_callback


def _get_state(ctx: Context) -> dict[str, Any]:
    st = ctx.get_state(STATE_KEY)
    if st is None:
        st = {}
        ctx.set_state(STATE_KEY, st)
    return st


def authenticate_and_get_config() -> SessionConfig | None:
    """从请求头中提取 token，并调用回调完成鉴权，返回会话配置。"""
    # ✅ 独立 fastmcp 官方方式：读取请求头
    headers: dict[str, str] = get_http_headers()  # 默认剔除不宜转发的头

    api_key = headers.get("X-API-Key")

    token: str
    if api_key:
        token = api_key.strip()
        if not token:
            logger.warning("Empty X-API-Key header received.")
            return None
        logger.info("Using X-API-Key header for authentication.")
    else:
        logger.warning(
            "Authentication failed: No Authorization or X-API-Key header found in request."
        )
        return None

    callback = _auth_callback
    if callback is None:
        logger.error("Authentication failed: No auth callback provided.")
        return None

    try:
        cfg = callback(token)
        if cfg is None:
            logger.warning(
                "Authentication failed: The provided token was rejected by the auth service."
            )
        else:
            logger.info("Authentication succeeded.")
        return cfg
    except Exception as e:
        logger.error("Auth callback execution failed", error=str(e), exc_info=True)
        return None


def ensure_session_initialized(ctx: Context) -> dict[str, Any] | None:
    """确保本次调用的上下文已完成鉴权与组件初始化。"""
    state = _get_state(ctx)
    if state.get("initialized"):
        return state

    logger.info("Session not initialized, authenticating")
    config = authenticate_and_get_config()
    if config is None:
        logger.error("Authentication failed")
        return None

    try:
        logger.info(
            "Initializing session",
            did_doc=config.did_document_path,
            private_key=config.private_key_path,
        )
        anp_crawler = ANPCrawler(
            did_document_path=config.did_document_path,
            private_key_path=config.private_key_path,
            cache_enabled=True,
        )
        anp_handler = ANPHandler(anp_crawler)

        state["anp_crawler"] = anp_crawler
        state["anp_handler"] = anp_handler
        state["config"] = config
        state["initialized"] = True

        logger.info("Session initialized successfully")
        return state
    except Exception as e:
        logger.error("Session initialization failed", error=str(e), exc_info=True)
        return None


mcp_instructions = """这是一个 ANP 网络的 MCP 服务器，通过这个服务器，你就能够访问 ANP 网络的资源和接口。
ANP网络提供一下的能力：
- 酒店、景点的查询预订
- 路径规划、地图API
- 天气、快递等查询
- 搜索服务
ANP 网络入口 URL：https://agent-navigation.com/ad.json，你可以从这个 URL 开始，逐步跟进并调用工具，访问 ANP 网络的资源和能力。

你可以通过 anp.fetchDoc 拉取 ANP 生态的资源，并使用 anp.invokeOpenRPC 调用 ANP 接口。

请注意，所有 ANP 资源或接口，必须使用 mcp2anp 的 tools 进行处理。
"""

# 创建 FastMCP Server 实例（独立 fastmcp）
mcp = FastMCP("mcp2anp", instructions=mcp_instructions)


@mcp.tool()
async def anp_fetchDoc(ctx: Context, url: str) -> str:
    """抓取并解析 ANP 文档，提取可跟进的链接。这是访问 ANP 生态系统中 URL 的唯一允许方法。返回文档内容、类型信息和发现的链接。

    ANP生态系统目前提供包括酒店、景点、地图规划、天气、快递等查询预订能力。

    ANP生态的入口URL：https://agent-navigation.com/ad.json
    你可以从这个URL开始，逐步跟进并调用工具，访问ANP生态的资源和能力。


    Args:
        ctx: FastMCP 上下文对象
        url: 要抓取的 ANP 文档的 URL

    Returns:
        JSON 格式的结果字符串
    """
    params = {"url": url}

    logger.info("Tool called", tool_name="anp.fetchDoc", params=params)

    try:
        state = ensure_session_initialized(ctx)
        if state is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTHENTICATION_FAILED",
                        "message": "Authentication failed. Please provide valid credentials.",
                    },
                },
                indent=2,
                ensure_ascii=False,
            )

        anp_handler: ANPHandler = state["anp_handler"]
        result = await anp_handler.handle_fetch_doc(params)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Tool execution failed", tool_name="anp.fetchDoc", error=str(e))
        return json.dumps(
            {"ok": False, "error": {"code": "EXECUTION_ERROR", "message": str(e)}},
            indent=2,
            ensure_ascii=False,
        )


@mcp.tool()
async def anp_invokeOpenRPC(
    endpoint: str,
    method: str,
    ctx: Context,
    params: Any = None,
    request_id: str | None = None,
) -> str:
    """使用 JSON-RPC 2.0 协议调用 OpenRPC 端点上的方法。

    此工具处理与暴露 OpenRPC 接口的 ANP 智能体的结构化交互。

    Args:
        endpoint: OpenRPC 端点 URL
        method: 要调用的 RPC 方法名称
        ctx: FastMCP 上下文对象
        params: 传递给方法的参数（可选）
        request_id: 用于跟踪的可选请求 ID

    Returns:
        JSON 格式的结果字符串
    """
    arguments: dict[str, Any] = {"endpoint": endpoint, "method": method}
    if params is not None:
        arguments["params"] = params
    if request_id is not None:
        arguments["id"] = request_id

    logger.info("Tool called", tool_name="anp.invokeOpenRPC", args=arguments)

    try:
        state = ensure_session_initialized(ctx)
        if state is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "AUTHENTICATION_FAILED",
                        "message": "Authentication failed. Please provide valid credentials.",
                    },
                },
                indent=2,
                ensure_ascii=False,
            )

        anp_handler: ANPHandler = state["anp_handler"]
        result = await anp_handler.handle_invoke_openrpc(arguments)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(
            "Tool execution failed", tool_name="anp.invokeOpenRPC", error=str(e)
        )
        return json.dumps(
            {"ok": False, "error": {"code": "EXECUTION_ERROR", "message": str(e)}},
            indent=2,
            ensure_ascii=False,
        )


@click.command()
@click.option(
    "--host",
    default="0.0.0.0",
    help="服务器监听地址",
)
@click.option(
    "--port",
    default=9880,
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
    """运行 MCP2ANP 远程桥接服务器（HTTP 模式，支持 X-API-Key）。"""
    setup_logging(log_level)

    # 设置远程验证回调
    auth_api_url = f"http://{AUTH_HOST}:{AUTH_PORT}{AUTH_VERIFY_PATH}"
    logger.info(f"{auth_api_url=}")
    remote_auth_callback = create_did_auth_callback(
        auth_api_url, api_key_header="X-API-Key"
    )
    set_auth_callback(remote_auth_callback)

    logger.info("Starting MCP2ANP remote server", host=host, port=port)

    try:
        app = app = mcp.http_app()
        uvicorn.run(app, host=host, port=port, log_level=log_level.lower(), ws="none")
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main()
