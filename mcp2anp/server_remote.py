"""远程 MCP 服务器实现（基于 MCP 官方 SDK FastMCP + Streamable HTTP）。"""

import json
from typing import Any

import click
import structlog
import uvicorn
from mcp.server.fastmcp import FastMCP

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


def initialize_server() -> None:
    """初始化远程服务器。"""
    global anp_handler

    anp_crawler = initialize_anp_crawler()
    anp_handler = ANPHandler(anp_crawler)

    logger.info("Remote MCP server initialized")


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
    default=8000,
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
    """运行 MCP2ANP 远程桥接服务器（HTTP 模式）。

    环境变量:
        ANP_DID_DOCUMENT_PATH: DID 文档 JSON 文件路径
        ANP_DID_PRIVATE_KEY_PATH: DID 私钥 PEM 文件路径

    如果未设置环境变量，将使用默认的公共 DID 凭证。

    使用示例：
        # 启动服务器
        uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 8000

        # 在 Claude Code 中添加远程服务器
        claude mcp add --transport http mcp2anp-remote http://YOUR_IP:8000/mcp
    """
    setup_logging(log_level)

    # 初始化 ANP handler
    initialize_server()

    logger.info("Starting MCP2ANP remote server", host=host, port=port)

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
