"""远程 MCP 服务器实现（基于 MCP 官方 SDK FastMCP + Streamable HTTP）。"""

import json
from collections.abc import Callable
from typing import Any

import click
import structlog
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware

from .core.handlers import ANPHandler, initialize_anp_crawler
from .utils import setup_logging

logger = structlog.get_logger(__name__)

mcp_instructions = """这是一个ANP网络的MCP服务器，通过这个服务器，你就能够访问ANP网络的资源和接口。
ANP网络提供一下的能力：
- 酒店、景点的查询预订
- 路径规划、地图API
- 天气、快递等查询
- 搜索服务

ANP网络的入口URL：https://agent-navigation.com/ad.json

你可以通过anp.fetchDoc工具，拉取ANP网络生态的资源，并使用anp.invokeOpenRPC调用ANP网络的接口。

请注意，所有ANP网络的资源或接口，必须使用mcp2anp的tools进行处理。
"""

# 创建 FastMCP Server 实例
mcp = FastMCP("mcp2anp", instructions=mcp_instructions)

# 全局状态：ANPHandler 实例（在启动时初始化）
anp_handler: ANPHandler | None = None

# 鉴权回调函数类型定义
AuthCallback = Callable[[str], bool]

# 全局鉴权回调函数
auth_callback: AuthCallback | None = None


def initialize_server() -> None:
    """初始化远程服务器。"""
    global anp_handler

    anp_crawler = initialize_anp_crawler()
    anp_handler = ANPHandler(anp_crawler)

    logger.info("Remote MCP server initialized")


def set_auth_callback(callback: AuthCallback) -> None:
    """设置鉴权回调函数。

    Args:
        callback: 鉴权回调函数，接收token字符串，返回bool表示是否通过验证
    """
    global auth_callback
    auth_callback = callback
    logger.info("Auth callback set")


def default_auth_callback(token: str) -> bool:
    """默认鉴权回调函数，打印token并通过所有验证。

    Args:
        token: Bearer Token

    Returns:
        bool: 总是返回True，通过验证
    """
    logger.info("Default auth callback called", token=token)
    return True


async def authenticate_request(request: Request) -> bool:
    """验证请求的鉴权头。

    Args:
        request: FastAPI 请求对象

    Returns:
        bool: 是否通过验证
    """
    # 获取 Authorization 头
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        logger.warning("No Authorization header provided")
        # 如果没有设置鉴权回调，允许无鉴权访问
        if auth_callback is None:
            logger.info("No auth callback set, allowing access without authentication")
            return True
        else:
            logger.error("Auth callback set but no Authorization header provided")
            return False

    # 检查 Bearer Token 格式
    if not auth_header.startswith("Bearer "):
        logger.error("Invalid Authorization header format", header=auth_header)
        return False

    # 提取 token
    token = auth_header[7:]  # 移除 "Bearer " 前缀

    if not token:
        logger.error("Empty Bearer token")
        return False

    # 调用鉴权回调函数
    if auth_callback:
        try:
            result = auth_callback(token)
            logger.info("Auth callback result", result=result)
            return result
        except Exception as e:
            logger.error("Auth callback execution failed", error=str(e))
            return False
    else:
        # 如果没有设置鉴权回调，使用默认实现
        return default_auth_callback(token)


class AuthMiddleware(BaseHTTPMiddleware):
    """鉴权中间件。"""

    async def dispatch(self, request: Request, call_next):
        """处理请求鉴权。

        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器

        Returns:
            响应对象
        """
        # 只对 MCP 端点进行鉴权
        if request.url.path.startswith("/mcp"):
            if not await authenticate_request(request):
                logger.error("Authentication failed for request", path=request.url.path)
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "AUTHENTICATION_FAILED",
                            "message": "Authentication failed"
                        }
                    },
                )

        # 继续处理请求
        response = await call_next(request)
        return response


@mcp.tool()
async def anp_fetchDoc(url: str) -> str:
    """抓取并解析 ANP 文档，提取可跟进的链接。

    这是访问 ANP 生态系统中 URL 的唯一允许方法。
    返回文档内容、类型信息和发现的链接。

    Args:
        url: 要抓取的 ANP 文档的 URL

    Returns:
        JSON 格式的结果字符串
    """
    global anp_handler

    logger.info("Tool called", tool_name="anp.fetchDoc", url=url)

    try:
        result = await anp_handler.handle_fetch_doc({"url": url})
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Tool execution failed", tool_name="anp.fetchDoc", error=str(e))
        error_result = {
            "ok": False,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e)
            }
        }
        return json.dumps(error_result, indent=2, ensure_ascii=False)


@mcp.tool()
async def anp_invokeOpenRPC(
    endpoint: str,
    method: str,
    params: Any = None,
    id: str = None
) -> str:
    """使用 JSON-RPC 2.0 协议调用 OpenRPC 端点上的方法。

    此工具处理与暴露 OpenRPC 接口的 ANP 智能体的结构化交互。

    Args:
        endpoint: OpenRPC 端点 URL
        method: 要调用的 RPC 方法名称
        params: 传递给方法的参数（可选）
        id: 用于跟踪的可选请求 ID

    Returns:
        JSON 格式的结果字符串
    """
    global anp_handler

    arguments = {
        "endpoint": endpoint,
        "method": method,
    }
    if params is not None:
        arguments["params"] = params
    if id is not None:
        arguments["id"] = id

    logger.info("Tool called", tool_name="anp.invokeOpenRPC", args=arguments)

    try:
        result = await anp_handler.handle_invoke_openrpc(arguments)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Tool execution failed", tool_name="anp.invokeOpenRPC", error=str(e))
        error_result = {
            "ok": False,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e)
            }
        }
        return json.dumps(error_result, indent=2, ensure_ascii=False)


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
@click.option(
    "--enable-auth",
    is_flag=True,
    default=False,
    help="启用Bearer Token鉴权（需要Authorization头）",
)
@click.option(
    "--auth-token",
    default=None,
    help="设置简单的固定Bearer Token（用于测试）",
)
def main(host: str, port: int, log_level: str, enable_auth: bool, auth_token: str) -> None:
    """运行 MCP2ANP 远程桥接服务器（HTTP 模式）。

    环境变量:
        ANP_DID_DOCUMENT_PATH: DID 文档 JSON 文件路径
        ANP_DID_PRIVATE_KEY_PATH: DID 私钥 PEM 文件路径
        MCP_AUTH_TOKEN: Bearer Token（如果启用鉴权）

    如果未设置环境变量，将使用默认的公共 DID 凭证。

    鉴权说明:
        默认情况下，服务器不启用鉴权。使用 --enable-auth 启用鉴权后：
        1. 如果设置了 --auth-token，将验证请求的 token 是否匹配
        2. 如果没有设置 --auth-token，将使用默认回调（打印token并通过）
        3. 也可以通过 set_auth_callback() 设置自定义鉴权逻辑

    使用示例：
        # 启动服务器（无鉴权）
        uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

        # 启动服务器（启用鉴权，使用固定token）
        uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token my-secret-token

        # 在 Claude Code 中添加远程服务器（无鉴权）
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp

        # 在 Claude Code 中添加远程服务器（有鉴权）
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp --header "Authorization: Bearer my-secret-token"

        # 使用 curl 测试（有鉴权）
        curl -X POST http://YOUR_IP:9880/mcp \\
             -H "Authorization: Bearer my-secret-token" \\
             -H "Content-Type: application/json" \\
             -d '{"method":"anp.fetchDoc","params":{"url":"https://agent-navigation.com/ad.json"}}'
    """
    setup_logging(log_level)

    # 初始化 ANP handler
    initialize_server()

    # 配置鉴权
    if enable_auth:
        if auth_token:
            # 使用固定 token 的简单鉴权
            def simple_auth_callback(token: str) -> bool:
                is_valid = token == auth_token
                logger.info("Simple auth callback called", token=token, valid=is_valid)
                return is_valid
            set_auth_callback(simple_auth_callback)
            logger.info("Authentication enabled with fixed token")
        else:
            # 使用默认鉴权回调（打印token并通过）
            set_auth_callback(default_auth_callback)
            logger.info("Authentication enabled with default callback (always pass)")
    else:
        logger.info("Authentication disabled")

    logger.info("Starting MCP2ANP remote server", host=host, port=port, auth_enabled=enable_auth)

    try:
        # 使用 uvicorn 运行 FastMCP 的 Streamable HTTP app
        app = mcp.streamable_http_app()

        # 如果启用鉴权，添加鉴权中间件
        if enable_auth:
            app.add_middleware(AuthMiddleware)
            logger.info("Auth middleware added")

        uvicorn.run(app, host=host, port=port, log_level=log_level.lower())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main(
        host="0.0.0.0",
        port=9880,
        enable_auth=True,
        auth_token=None,
        log_level="INFO"
    )
