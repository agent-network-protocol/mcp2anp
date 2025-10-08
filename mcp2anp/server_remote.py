"""远程 MCP 服务器实现（基于 MCP 官方 SDK FastMCP + Streamable HTTP）。"""

import json
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

import click
import structlog
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware

from .session import SessionConfig, SessionManager, SessionState
from .utils import setup_logging

logger = structlog.get_logger(__name__)

# 使用 ContextVar 存储当前请求的会话状态
current_session: ContextVar[SessionState | None] = ContextVar("current_session", default=None)

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

# 全局会话管理器（在 main 函数中初始化）
session_manager: SessionManager | None = None

# 鉴权回调函数类型定义（返回 SessionConfig 或 None）
AuthCallback = Callable[[str], SessionConfig | None]

# 全局鉴权回调函数
auth_callback: AuthCallback | None = None


def initialize_server() -> None:
    """初始化远程服务器（有状态模式下不需要全局初始化）。"""
    logger.info("Remote MCP server initialized (stateful mode)")


def set_auth_callback(callback: AuthCallback) -> None:
    """设置鉴权回调函数。

    Args:
        callback: 鉴权回调函数，接收token字符串，返回SessionConfig或None
    """
    global auth_callback
    auth_callback = callback
    logger.info("Auth callback set")


def default_auth_callback(token: str) -> SessionConfig | None:
    """默认鉴权回调函数，使用默认的公共 DID 凭证。

    Args:
        token: Bearer Token

    Returns:
        SessionConfig: 使用默认公共 DID 凭证的配置
    """
    logger.info("Default auth callback called", token=token)

    # 使用默认的公共 DID 凭证
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    did_document_path = str(project_root / "docs" / "did_public" / "public-did-doc.json")
    private_key_path = str(project_root / "docs" / "did_public" / "public-private-key.pem")

    return SessionConfig(
        did_document_path=did_document_path,
        private_key_path=private_key_path
    )


async def authenticate_request(request: Request) -> tuple[bool, SessionConfig | None]:
    """验证请求的鉴权头并返回会话配置。

    Args:
        request: FastAPI 请求对象

    Returns:
        tuple[bool, SessionConfig | None]: (是否通过验证, 会话配置)
    """
    # 获取 Authorization 头
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        logger.warning("No Authorization header provided")
        # 如果没有设置鉴权回调，使用默认配置
        if auth_callback is None:
            logger.info("No auth callback set, using default config")
            return True, default_auth_callback("")
        else:
            logger.error("Auth callback set but no Authorization header provided")
            return False, None

    # 检查 Bearer Token 格式
    if not auth_header.startswith("Bearer "):
        logger.error("Invalid Authorization header format", header=auth_header)
        return False, None

    # 提取 token
    token = auth_header[7:]  # 移除 "Bearer " 前缀

    if not token:
        logger.error("Empty Bearer token")
        return False, None

    # 调用鉴权回调函数
    if auth_callback:
        try:
            config = auth_callback(token)
            if config is None:
                logger.error("Auth callback returned None (authentication failed)")
                return False, None
            logger.info("Auth callback succeeded")
            return True, config
        except Exception as e:
            logger.error("Auth callback execution failed", error=str(e))
            return False, None
    else:
        # 如果没有设置鉴权回调，使用默认实现
        config = default_auth_callback(token)
        return True, config


class AuthMiddleware(BaseHTTPMiddleware):
    """鉴权和会话管理中间件。"""

    async def dispatch(self, request: Request, call_next):
        """处理请求鉴权和会话管理。

        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器

        Returns:
            响应对象
        """
        # 只对 MCP 端点进行鉴权和会话管理
        if request.url.path.startswith("/mcp"):
            # 检查是否已有会话 ID
            session_id = request.headers.get("Mcp-Session-Id")

            if session_id:
                # 验证会话是否存在
                session_state = session_manager.get_session(session_id)
                if session_state:
                    logger.info("Using existing session", session_id=session_id)
                    # 将会话状态存储到请求状态中供工具使用
                    request.state.session_state = session_state
                    # 设置到 ContextVar
                    current_session.set(session_state)
                else:
                    logger.warning("Invalid session ID", session_id=session_id)
                    return JSONResponse(
                        status_code=401,
                        content={
                            "error": {
                                "code": "INVALID_SESSION",
                                "message": "Session not found or expired"
                            }
                        },
                    )
            else:
                # 新连接，进行鉴权并创建会话
                is_authenticated, config = await authenticate_request(request)

                if not is_authenticated or config is None:
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

                # 创建新会话
                try:
                    session_id = session_manager.create_session(config)
                    session_state = session_manager.get_session(session_id)
                    request.state.session_state = session_state
                    request.state.new_session_id = session_id
                    # 设置到 ContextVar
                    current_session.set(session_state)
                    logger.info("Created new session", session_id=session_id)
                except Exception as e:
                    logger.error("Failed to create session", error=str(e))
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": {
                                "code": "SESSION_CREATION_FAILED",
                                "message": str(e)
                            }
                        },
                    )

        # 继续处理请求
        response = await call_next(request)

        # 清理 ContextVar
        current_session.set(None)

        # 如果是新会话，在响应头中返回会话 ID
        if hasattr(request.state, "new_session_id"):
            response.headers["Mcp-Session-Id"] = request.state.new_session_id
            # CORS 需要显式暴露该头
            response.headers["Access-Control-Expose-Headers"] = "Mcp-Session-Id"
            logger.info("Session ID added to response", session_id=request.state.new_session_id)

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
    logger.info("Tool called", tool_name="anp.fetchDoc", url=url)

    try:
        # 从 ContextVar 获取当前会话
        session_state = current_session.get()
        if session_state is None or session_state.anp_handler is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "NO_SESSION",
                    "message": "No active session found. Please authenticate first."
                }
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        result = await session_state.anp_handler.handle_fetch_doc({"url": url})
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
        # 从 ContextVar 获取当前会话
        session_state = current_session.get()
        if session_state is None or session_state.anp_handler is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "NO_SESSION",
                    "message": "No active session found. Please authenticate first."
                }
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        result = await session_state.anp_handler.handle_invoke_openrpc(arguments)
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
@click.option(
    "--session-timeout",
    default=30,
    type=int,
    help="会话超时时间（秒），默认 30 秒",
)
@click.option(
    "--cleanup-interval",
    default=300,
    type=int,
    help="会话清理任务执行间隔（秒），默认 300 秒（5 分钟）",
)
def main(
    host: str,
    port: int,
    log_level: str,
    enable_auth: bool,
    auth_token: str,
    session_timeout: int,
    cleanup_interval: int
) -> None:
    """运行 MCP2ANP 远程桥接服务器（HTTP 模式，有状态会话）。

    环境变量:
        ANP_DID_DOCUMENT_PATH: DID 文档 JSON 文件路径（可选，默认使用公共凭证）
        ANP_DID_PRIVATE_KEY_PATH: DID 私钥 PEM 文件路径（可选，默认使用公共凭证）

    会话管理:
        服务器使用 Mcp-Session-Id 头进行会话管理：
        1. 首次连接时，服务器进行鉴权并创建会话，返回 Mcp-Session-Id
        2. 后续请求携带该头，服务器将复用会话状态（ANPCrawler 和 ANPHandler）
        3. 每个会话拥有独立的 DID 凭证和状态

    鉴权说明:
        默认情况下，服务器不启用鉴权，使用默认公共 DID 凭证。
        使用 --enable-auth 启用鉴权后：
        1. 如果设置了 --auth-token，将验证请求的 token 是否匹配
        2. 如果没有设置 --auth-token，将使用默认回调（使用公共凭证）
        3. 也可以通过 set_auth_callback() 设置自定义鉴权逻辑
           自定义回调应返回 SessionConfig(did_document_path, private_key_path)

    使用示例：
        # 启动服务器（无鉴权，使用默认公共凭证）
        uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

        # 启动服务器（启用鉴权，使用固定token）
        uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token my-secret-token

        # 在 Claude Code 中添加远程服务器（无鉴权）
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp

        # 在 Claude Code 中添加远程服务器（有鉴权）
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp --header "Authorization: Bearer my-secret-token"

        # 使用 curl 测试（首次请求）
        curl -X POST http://YOUR_IP:9880/mcp \\
             -H "Authorization: Bearer my-secret-token" \\
             -H "Content-Type: application/json" \\
             -d '{"method":"anp.fetchDoc","params":{"url":"https://agent-navigation.com/ad.json"}}' \\
             -i  # 查看响应头中的 Mcp-Session-Id

        # 后续请求携带会话 ID
        curl -X POST http://YOUR_IP:9880/mcp \\
             -H "Mcp-Session-Id: <session-id-from-first-response>" \\
             -H "Content-Type: application/json" \\
             -d '{"method":"anp.invokeOpenRPC","params":{...}}'
    """
    setup_logging(log_level)

    # 初始化服务器
    initialize_server()

    # 配置鉴权
    if enable_auth:
        if auth_token:
            # 使用固定 token 的简单鉴权
            def simple_auth_callback(token: str) -> SessionConfig | None:
                is_valid = token == auth_token
                logger.info("Simple auth callback called", token=token, valid=is_valid)
                if is_valid:
                    return default_auth_callback(token)
                return None
            set_auth_callback(simple_auth_callback)
            logger.info("Authentication enabled with fixed token")
        else:
            # 使用默认鉴权回调（使用公共凭证）
            set_auth_callback(default_auth_callback)
            logger.info("Authentication enabled with default callback (public credentials)")
    else:
        logger.info("Authentication disabled (using default public credentials)")

    # 配置会话管理器的超时参数
    global session_manager
    session_manager = SessionManager(timeout=session_timeout, cleanup_interval=cleanup_interval)

    logger.info(
        "Starting MCP2ANP remote server (stateful mode)",
        host=host,
        port=port,
        auth_enabled=enable_auth,
        session_timeout=session_timeout,
        cleanup_interval=cleanup_interval
    )

    try:
        # 使用 uvicorn 运行 FastMCP 的 Streamable HTTP app
        app = mcp.streamable_http_app()

        # 添加会话管理中间件（总是需要，用于管理会话状态）
        app.add_middleware(AuthMiddleware)
        logger.info("Session management middleware added")

        # 添加启动事件处理器来启动清理任务
        @app.on_event("startup")
        async def startup_event():
            """服务器启动时启动清理任务。"""
            session_manager.start_cleanup_task()
            logger.info("Cleanup task started on server startup")

        # 添加关闭事件处理器来停止清理任务
        @app.on_event("shutdown")
        async def shutdown_event():
            """服务器关闭时停止清理任务。"""
            session_manager.stop_cleanup_task()
            logger.info("Cleanup task stopped on server shutdown")

        uvicorn.run(app, host=host, port=port, log_level=log_level.lower())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        session_manager.stop_cleanup_task()
    except Exception as e:
        logger.error("Server error", error=str(e))
        session_manager.stop_cleanup_task()
        raise


if __name__ == "__main__":
    main()
