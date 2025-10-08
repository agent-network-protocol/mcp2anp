"""远程 MCP 服务器实现（基于 MCP 官方 SDK FastMCP + Streamable HTTP）。"""

import json
from collections.abc import Callable
from typing import Any
from weakref import WeakKeyDictionary

import click
import structlog
import uvicorn
from agent_connect.anp_crawler.anp_crawler import ANPCrawler
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from .core.handlers import ANPHandler
from .utils import setup_logging

logger = structlog.get_logger(__name__)

# 使用 WeakKeyDictionary 存储每个 ServerSession 的状态
SESSION_STORE: WeakKeyDictionary[ServerSession, dict[str, Any]] = WeakKeyDictionary()


class SessionConfig:
    """会话配置信息。

    存储会话所需的 DID 凭证路径。
    """

    def __init__(self, did_document_path: str, private_key_path: str):
        """初始化会话配置。

        Args:
            did_document_path: DID 文档 JSON 文件路径
            private_key_path: DID 私钥 PEM 文件路径
        """
        self.did_document_path = did_document_path
        self.private_key_path = private_key_path


# 鉴权回调函数类型定义（接收 token 字符串，返回 SessionConfig 或 None）
AuthCallback = Callable[[str], SessionConfig | None]

# 全局鉴权回调函数
_auth_callback: AuthCallback | None = None


def get_session_state(session: ServerSession) -> dict[str, Any]:
    """获取或创建会话状态。

    Args:
        session: FastMCP 的 ServerSession 实例

    Returns:
        dict: 会话状态字典
    """
    if session not in SESSION_STORE:
        SESSION_STORE[session] = {}
    return SESSION_STORE[session]


def initialize_session(session: ServerSession, config: SessionConfig) -> None:
    """初始化会话的 ANPCrawler 和 ANPHandler。

    Args:
        session: FastMCP 的 ServerSession 实例
        config: 会话配置

    Raises:
        Exception: 初始化失败时抛出异常
    """
    state = get_session_state(session)

    # 如果已初始化，则跳过
    if "initialized" in state and state["initialized"]:
        logger.info("Session already initialized", session_id=id(session))
        return

    try:
        logger.info(
            "Initializing session",
            session_id=id(session),
            did_doc=config.did_document_path,
            private_key=config.private_key_path,
        )

        # 创建 ANPCrawler 实例
        anp_crawler = ANPCrawler(
            did_document_path=config.did_document_path,
            private_key_path=config.private_key_path,
            cache_enabled=True
        )

        # 创建 ANPHandler 实例
        anp_handler = ANPHandler(anp_crawler)

        # 存储到会话状态
        state["anp_crawler"] = anp_crawler
        state["anp_handler"] = anp_handler
        state["config"] = config
        state["initialized"] = True

        logger.info("Session initialized successfully", session_id=id(session))

    except Exception as e:
        logger.error("Failed to initialize session", session_id=id(session), error=str(e))
        raise


mcp_instructions = """这是一个ANP网络的MCP服务器，通过这个服务器，你就能够访问ANP网络的资源和接口。
ANP网络提供一下的能力：
- 酒店、景点的查询预订
- 路径规划、地图API
- 天气、快递等查询
- 搜索服务

ANP网络的入口URL：https://agent-navigation.com/ad.json，你可以从这个URL开始，逐步跟进并调用工具，访问ANP网络的资源和能力。

你可以通过anp.fetchDoc工具，拉取ANP网络生态的资源，并使用anp.invokeOpenRPC调用ANP网络的接口。

请注意，所有ANP网络的资源或接口，必须使用mcp2anp的tools进行处理。
"""

# 创建 FastMCP Server 实例
mcp = FastMCP("mcp2anp", instructions=mcp_instructions)


def get_default_config() -> SessionConfig:
    """获取默认的会话配置（使用公共 DID 凭证）。

    Returns:
        SessionConfig: 默认配置
    """
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    did_document_path = str(project_root / "docs" / "did_public" / "public-did-doc.json")
    private_key_path = str(project_root / "docs" / "did_public" / "public-private-key.pem")

    return SessionConfig(
        did_document_path=did_document_path,
        private_key_path=private_key_path
    )


def default_auth_callback(token: str) -> SessionConfig | None:
    """默认鉴权回调函数，使用默认的公共 DID 凭证。

    Args:
        token: Bearer Token（本实现中不验证 token，总是返回默认配置）

    Returns:
        SessionConfig: 使用默认公共 DID 凭证的配置
    """
    logger.info("Default auth callback called", token=token[:10] + "..." if len(token) > 10 else token)
    return get_default_config()


def set_auth_callback(callback: AuthCallback | None) -> None:
    """设置自定义鉴权回调函数。

    Args:
        callback: 鉴权回调函数，接收 token 字符串，返回 SessionConfig 或 None。
                 如果返回 None，表示鉴权失败。
                 如果设置为 None，则使用默认鉴权回调。

    Example:
        def my_auth_callback(token: str) -> SessionConfig | None:
            if token == "my-secret-token":
                return SessionConfig(
                    did_document_path="/path/to/did.json",
                    private_key_path="/path/to/key.pem"
                )
            return None  # 鉴权失败

        set_auth_callback(my_auth_callback)
    """
    global _auth_callback
    _auth_callback = callback
    logger.info("Auth callback set", has_callback=callback is not None)


def authenticate_and_get_config(ctx: Context) -> SessionConfig | None:
    """从 Context 中提取 Authorization 头并进行鉴权。

    Args:
        ctx: FastMCP 上下文对象

    Returns:
        SessionConfig | None: 鉴权成功返回配置，失败返回 None
    """
    # 尝试从 Context 的 request_context 中获取 Authorization 头
    auth_header = None
    if hasattr(ctx, "request_context") and ctx.request_context:
        # FastMCP 的 request_context 可能包含 HTTP 头信息
        if isinstance(ctx.request_context, dict):
            auth_header = ctx.request_context.get("authorization") or ctx.request_context.get("Authorization")

    # 如果没有 Authorization 头，使用默认鉴权
    if not auth_header:
        logger.info("No Authorization header found, using default auth")
        callback = _auth_callback or default_auth_callback
        return callback("")

    # 检查 Bearer Token 格式
    if not auth_header.startswith("Bearer "):
        logger.warning("Invalid Authorization header format", header=auth_header[:20])
        return None

    # 提取 token
    token = auth_header[7:].strip()

    if not token:
        logger.warning("Empty Bearer token")
        return None

    # 调用鉴权回调函数
    callback = _auth_callback or default_auth_callback
    try:
        config = callback(token)
        if config is None:
            logger.warning("Auth callback returned None (authentication failed)")
        else:
            logger.info("Authentication succeeded")
        return config
    except Exception as e:
        logger.error("Auth callback execution failed", error=str(e))
        return None


def ensure_session_initialized(ctx: Context) -> dict[str, Any] | None:
    """确保会话已初始化，如果未初始化则进行鉴权并初始化。

    Args:
        ctx: FastMCP 上下文对象

    Returns:
        dict | None: 会话状态字典，如果鉴权失败返回 None
    """
    # 获取会话状态
    state = get_session_state(ctx.session)

    # 如果已初始化，直接返回
    if state.get("initialized"):
        return state

    # 未初始化，进行鉴权
    logger.info("Session not initialized, authenticating", session_id=id(ctx.session))
    config = authenticate_and_get_config(ctx)

    if config is None:
        logger.error("Authentication failed", session_id=id(ctx.session))
        return None

    # 初始化会话
    try:
        initialize_session(ctx.session, config)
        return get_session_state(ctx.session)
    except Exception as e:
        logger.error("Session initialization failed", session_id=id(ctx.session), error=str(e))
        return None




@mcp.tool()
async def anp_fetchDoc(url: str, ctx: Context) -> str:
    """抓取并解析 ANP 文档，提取可跟进的链接。这是访问 ANP 生态系统中 URL 的唯一允许方法。返回文档内容、类型信息和发现的链接。

    ANP生态系统目前提供包括酒店、景点、地图规划、天气、快递等查询预订能力。

    ANP生态的入口URL：https://agent-navigation.com/ad.json
    你可以从这个URL开始，逐步跟进并调用工具，访问ANP生态的资源和能力。

    Args:
        url: 要抓取的 ANP 文档的 URL
        ctx: FastMCP 上下文对象

    Returns:
        JSON 格式的结果字符串
    """
    logger.info("Tool called", tool_name="anp.fetchDoc", url=url, session_id=id(ctx.session))

    try:
        # 确保会话已初始化（包含鉴权）
        state = ensure_session_initialized(ctx)

        if state is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Authentication failed. Please provide valid credentials."
                }
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        anp_handler = state.get("anp_handler")
        if anp_handler is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "SESSION_NOT_INITIALIZED",
                    "message": "Session handler not available"
                }
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

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
    ctx: Context,
    params: Any = None,
    request_id: str = None
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
    arguments = {
        "endpoint": endpoint,
        "method": method,
    }
    if params is not None:
        arguments["params"] = params
    if request_id is not None:
        arguments["id"] = request_id

    logger.info("Tool called", tool_name="anp.invokeOpenRPC", args=arguments, session_id=id(ctx.session))

    try:
        # 确保会话已初始化（包含鉴权）
        state = ensure_session_initialized(ctx)

        if state is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Authentication failed. Please provide valid credentials."
                }
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        anp_handler = state.get("anp_handler")
        if anp_handler is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "SESSION_NOT_INITIALIZED",
                    "message": "Session handler not available"
                }
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

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
def main(
    host: str,
    port: int,
    log_level: str,
) -> None:
    """运行 MCP2ANP 远程桥接服务器（HTTP 模式，使用 FastMCP 会话管理）。

    环境变量:
        ANP_DID_DOCUMENT_PATH: DID 文档 JSON 文件路径（可选，默认使用公共凭证）
        ANP_DID_PRIVATE_KEY_PATH: DID 私钥 PEM 文件路径（可选，默认使用公共凭证）

    会话管理:
        服务器使用 FastMCP 内置的会话管理机制：
        1. 每个客户端连接都有独立的 ServerSession 实例
        2. 每个会话自动创建独立的 ANPCrawler 和 ANPHandler
        3. 使用 WeakKeyDictionary 管理会话状态，自动释放内存
        4. 默认使用公共 DID 凭证

    使用示例：
        # 启动服务器
        uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

        # 在 Claude Code 中添加远程服务器
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp

        # 使用 curl 测试
        curl -X POST http://YOUR_IP:9880/mcp \\
             -H "Content-Type: application/json" \\
             -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}},"id":1}'
    """
    setup_logging(log_level)

    logger.info(
        "Starting MCP2ANP remote server (FastMCP session management)",
        host=host,
        port=port,
    )

    try:
        # 使用 uvicorn 运行 FastMCP 的 Streamable HTTP app
        app = mcp.streamable_http_app()

        uvicorn.run(app, host=host, port=port, log_level=log_level.lower())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main()
