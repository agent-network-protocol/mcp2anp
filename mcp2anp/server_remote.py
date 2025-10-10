"""远程 MCP 服务器实现（基于 MCP 官方 SDK FastMCP + Streamable HTTP）。"""

import json
import subprocess
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

# 远程认证服务配置
# TODO: 后面改为 didhost.cc
AUTH_HOST = "127.0.0.1"
AUTH_PORT = 9866
AUTH_VERIFY_PATH = "/api/v1/mcp-sk-api-keys/verify"


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
            cache_enabled=True,
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
        logger.error(
            "Failed to initialize session", session_id=id(session), error=str(e)
        )
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
    did_document_path = str(
        project_root / "docs" / "did_public" / "public-did-doc.json"
    )
    private_key_path = str(
        project_root / "docs" / "did_public" / "public-private-key.pem"
    )

    return SessionConfig(
        did_document_path=did_document_path, private_key_path=private_key_path
    )


from pydantic import BaseModel, ValidationError


class DidAuthResponse(BaseModel):
    """API 响应模型，用于验证远程认证服务返回的数据。"""

    did: str
    did_doc_path: str
    private_pem_path: str


def create_did_auth_callback(
    verify_url: str, api_key_header: str = "X-API-Key"
) -> AuthCallback:
    """创建一个通过远程 API 验证 token 并返回 DID 配置的回调函数。"""

    def did_auth_callback(token: str) -> SessionConfig | None:
        """调用远程 API 验证 token 并获取会话信息。"""
        if not token:
            logger.warning("DID auth callback received an empty token.")
            return None

        cmd = [
            "curl",
            "-sS",
            "-m",
            "15",
            "-H",
            f"{api_key_header}: {token}",
            "-w",
            "\n%{http_code}",
            verify_url,
        ]

        logger.info(
            "Calling remote auth service to verify key via curl",
            url=verify_url,
            command=" ".join(cmd[:-1] + [verify_url]),
        )

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as e:
            logger.error("curl executable not found", error=str(e))
            return None

        if result.returncode != 0:
            logger.error(
                "curl command failed",
                returncode=result.returncode,
                stderr=result.stderr.strip(),
            )
            return None

        output_lines = result.stdout.splitlines()
        if not output_lines:
            logger.error("curl returned empty response")
            return None

        status_line = output_lines[-1]
        body = "\n".join(output_lines[:-1])

        try:
            status_code = int(status_line)
        except ValueError:
            logger.error(
                "Failed to parse status code from curl output",
                status_line=status_line,
                raw_output=result.stdout,
            )
            return None

        if status_code == 200:
            try:
                payload = json.loads(body) if body else {}
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
                    response_data=body,
                )
                return None

        if status_code == 401:
            logger.warning(
                "Remote auth failed: Invalid or missing API Key.",
                response=body,
            )
            return None

        logger.error(
            "Remote auth service returned an error",
            status_code=status_code,
            response=body,
        )
        return None

    return did_auth_callback


def default_auth_callback(token: str) -> SessionConfig | None:
    """默认鉴权回调函数，使用默认的公共 DID 凭证。

    Args:
        token: Bearer Token（本实现中不验证 token，总是返回默认配置）

    Returns:
        SessionConfig: 使用默认公共 DID 凭证的配置
    """
    logger.info(
        "Default auth callback called",
        token=token[:10] + "..." if len(token) > 10 else token,
    )
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
    """从 Context 中提取请求头并进行鉴权。

    Args:
        ctx: FastMCP 上下文对象

    Returns:
        SessionConfig | None: 鉴权成功返回配置，失败返回 None
    """
    headers: dict[str, Any] = {}

    if hasattr(ctx, "request_context") and ctx.request_context:
        if isinstance(ctx.request_context, dict):
            headers = {
                str(key).lower(): value
                for key, value in ctx.request_context.items()
                if isinstance(key, str)
            }

    auth_header = headers.get("authorization")
    api_key_header = headers.get("x-api-key")

    token: str | None = None
    if api_key_header:
        token = str(api_key_header).strip()
        if not token:
            logger.warning("Empty X-API-Key header")
            return None
        logger.info("Using X-API-Key header for authentication")
    elif auth_header:
        if not auth_header.startswith("Bearer "):
            logger.warning(
                "Invalid Authorization header format", header=auth_header[:20]
            )
            return None
        token = auth_header[7:].strip()
        if not token:
            logger.warning("Empty Bearer token")
            return None
    else:
        logger.info("No Authorization or X-API-Key header found, using default auth")
        callback = _auth_callback or default_auth_callback
        return callback("")

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
        logger.error(
            "Session initialization failed", session_id=id(ctx.session), error=str(e)
        )
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
    logger.info(
        "Tool called", tool_name="anp.fetchDoc", url=url, session_id=id(ctx.session)
    )

    try:
        # 确保会话已初始化（包含鉴权）
        state = ensure_session_initialized(ctx)

        if state is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Authentication failed. Please provide valid credentials.",
                },
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        anp_handler = state.get("anp_handler")
        if anp_handler is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "SESSION_NOT_INITIALIZED",
                    "message": "Session handler not available",
                },
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        result = await anp_handler.handle_fetch_doc({"url": url})
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Tool execution failed", tool_name="anp.fetchDoc", error=str(e))
        error_result = {
            "ok": False,
            "error": {"code": "EXECUTION_ERROR", "message": str(e)},
        }
        return json.dumps(error_result, indent=2, ensure_ascii=False)


@mcp.tool()
async def anp_invokeOpenRPC(
    endpoint: str, method: str, ctx: Context, params: Any = None, request_id: str = None
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

    logger.info(
        "Tool called",
        tool_name="anp.invokeOpenRPC",
        args=arguments,
        session_id=id(ctx.session),
    )

    try:
        # 确保会话已初始化（包含鉴权）
        state = ensure_session_initialized(ctx)

        if state is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Authentication failed. Please provide valid credentials.",
                },
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        anp_handler = state.get("anp_handler")
        if anp_handler is None:
            error_result = {
                "ok": False,
                "error": {
                    "code": "SESSION_NOT_INITIALIZED",
                    "message": "Session handler not available",
                },
            }
            return json.dumps(error_result, indent=2, ensure_ascii=False)

        result = await anp_handler.handle_invoke_openrpc(arguments)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(
            "Tool execution failed", tool_name="anp.invokeOpenRPC", error=str(e)
        )
        error_result = {
            "ok": False,
            "error": {"code": "EXECUTION_ERROR", "message": str(e)},
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
    "--api-key",
    envvar="MCP_API_KEY",
    help="用于远程验证的 API Key。如果提供，将覆盖默认的公共 DID。",
)
def main(
    host: str,
    port: int,
    log_level: str,
    api_key: str | None,
) -> None:
    """运行 MCP2ANP 远程桥接服务器（HTTP 模式，使用 FastMCP 会话管理）。

    该服务器提供对 ANP 网络资源的访问。

    认证方式:
    1.  **API Key (推荐)**:
        通过 `--api-key` 参数或 `MCP_API_KEY` 环境变量提供 API Key。
        服务器将在启动时使用此 Key 从认证服务获取专用的 DID 凭证。
        这为每个服务器实例提供了独立的身份标识。

        示例:
        `uv run python -m mcp2anp.server_remote --api-key "your-secret-api-key"`

    2.  **默认公共凭证**:
        如果未提供 API Key，服务器将使用一个内置的、所有实例共享的公共 DID 凭证。
        这适用于快速测试或不需要独立身份的场景。

    使用示例：
        # 启动服务器 (使用 API Key)
        uv run python -m mcp2anp.server_remote --api-key "your-key"

        # 在 Claude Code 中添加远程服务器
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp

        # 使用 curl 测试 (无 Bearer Token，因为服务器配置了全局身份)
        curl -X POST http://YOUR_IP:9880/mcp \
             -H "Content-Type: application/json" \
             -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}},"id":1}'
    """
    setup_logging(log_level)

    if api_key:
        auth_api_url = f"http://{AUTH_HOST}:{AUTH_PORT}{AUTH_VERIFY_PATH}"
        logger.info(
            "API key provided, attempting remote authentication...", url=auth_api_url
        )
        remote_auth_callback = create_did_auth_callback(
            auth_api_url, api_key_header="X-API-Key"
        )
        session_config = remote_auth_callback(api_key)

        if session_config is None:
            logger.error(
                "Failed to authenticate with remote server. Please check auth service and API key.",
                api_key=api_key[:6] + "***",
            )
            return

        logger.info("Remote authentication successful")

        def auth_callback(token: str) -> SessionConfig | None:
            cleaned_token = token.strip() if token else ""
            if cleaned_token:
                return remote_auth_callback(cleaned_token)
            return session_config

        set_auth_callback(auth_callback)
        logger.info("Auth callback set to resolve session credentials via X-API-Key.")
    else:
        logger.info(
            "No API key provided. Using default public DID credentials for all sessions."
        )
        # 使用默认回调
        set_auth_callback(default_auth_callback)

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
