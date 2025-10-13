"""MCP server implementation for ANP bridge (本地 stdio 模式)。"""

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import click
import mcp.server.stdio
import structlog
from mcp.server import Server
from mcp.types import TextContent, Tool

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
# 创建 MCP Server 实例
server = Server("mcp2anp", instructions=mcp_instructions)

# 全局状态：ANPHandler 实例（在启动时初始化）
anp_handler: ANPHandler | None = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """返回可用工具列表。"""
    return [
        Tool(
            name="anp.fetchDoc",
            description=(
                "抓取并解析 ANP 文档，提取可跟进的链接。这是访问 ANP 生态系统中 URL 的唯一允许方法。返回文档内容、类型信息和发现的链接。"

                "ANP生态系统目前提供包括酒店、景点、地图规划、天气、快递等查询预订能力。"

                "ANP生态的入口URL：https://agent-navigation.com/ad.json"
                "你可以从这个URL开始，逐步跟进并调用工具，访问ANP生态的资源和能力。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要抓取的 ANP 文档的 URL",
                        "format": "uri",
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="anp.invokeOpenRPC",
            description=(
                "使用 JSON-RPC 2.0 协议调用 OpenRPC 端点上的方法。"
                "此工具处理与暴露 OpenRPC 接口的 ANP 智能体的结构化交互。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "OpenRPC 端点 URL",
                        "format": "uri",
                    },
                    "method": {
                        "type": "string",
                        "description": "要调用的 RPC 方法名称",
                    },
                    "params": {
                        "description": "传递给方法的参数",
                    },
                    "id": {
                        "type": "string",
                        "description": "用于跟踪的可选请求 ID",
                    },
                },
                "required": ["endpoint", "method"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """处理工具调用。"""
    global anp_handler

    logger.info("Tool called", tool_name=name, args=arguments)

    try:
        if name == "anp.fetchDoc":
            result = await anp_handler.handle_fetch_doc(arguments)
        elif name == "anp.invokeOpenRPC":
            result = await anp_handler.handle_invoke_openrpc(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        # 将结果转换为字符串格式返回
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    except Exception as e:
        logger.error("Tool execution failed", tool_name=name, error=str(e))
        error_result = {
            "ok": False,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e)
            }
        }
        return [TextContent(type="text", text=json.dumps(error_result, indent=2, ensure_ascii=False))]


def initialize_server() -> None:
    """初始化本地服务器。"""
    global anp_handler

    anp_crawler = initialize_anp_crawler()
    anp_handler = ANPHandler(anp_crawler)

    logger.info("Local MCP server initialized")


async def run_server():
    """运行 MCP 服务器。"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


@click.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="设置日志级别",
)
@click.option(
    "--reload",
    is_flag=True,
    help="启用开发热重载",
)
def main(log_level: str, reload: bool) -> None:
    """运行 MCP2ANP 本地桥接服务器（stdio 模式）。

    环境变量:
        ANP_DID_DOCUMENT_PATH: DID 文档 JSON 文件路径
        ANP_DID_PRIVATE_KEY_PATH: DID 私钥 PEM 文件路径

    如果未设置环境变量，将使用默认的公共 DID 凭证。
    """
    setup_logging(log_level)

    # 初始化服务器
    initialize_server()

    if reload:
        logger.info("Starting MCP2ANP local server with hot reload enabled")
    else:
        logger.info("Starting MCP2ANP local server")

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main()
