"""MCP server implementation for ANP bridge."""

import asyncio
from collections.abc import Sequence
from typing import Any

import click
import mcp.server.stdio
import structlog
from mcp.server import Server
from mcp.types import TextContent, Tool

from .auth import SessionManager
from .tools import FetchDocTool, InvokeOpenRPCTool, SetAuthTool
from .utils import setup_logging

logger = structlog.get_logger(__name__)

# 创建 MCP Server 实例
server = Server("mcp2anp")

# 全局会话管理器
session_manager = SessionManager()

# 初始化工具
fetch_doc_tool = FetchDocTool(session_manager)
invoke_openrpc_tool = InvokeOpenRPCTool(session_manager)
set_auth_tool = SetAuthTool(session_manager)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """返回可用工具列表。"""
    return [
        Tool(
            name="anp.setAuth",
            description=(
                "设置 DID 认证上下文。使用本地 DID 文档和私钥文件建立认证，"
                "后续的 fetchDoc 和 invokeOpenRPC 调用将自动使用这些凭证。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "did_document_path": {
                        "type": "string",
                        "description": "DID 文档 JSON 文件的路径",
                    },
                    "did_private_key_path": {
                        "type": "string",
                        "description": "DID 私钥 PEM 文件的路径",
                    },
                },
                "required": ["did_document_path", "did_private_key_path"],
            },
        ),
        Tool(
            name="anp.fetchDoc",
            description=(
                "抓取并解析 ANP 文档，提取可跟进的链接。"
                "这是访问 ANP 生态系统中 URL 的唯一允许方法。"
                "返回文档内容、类型信息和发现的链接。"
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
                        "type": "object",
                        "description": "传递给方法的参数",
                        "default": {},
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
    logger.info("Tool called", tool_name=name, args=arguments)

    try:
        if name == "anp.setAuth":
            result = await set_auth_tool.execute({
                "didDocumentPath": arguments.get("did_document_path"),
                "didPrivateKeyPath": arguments.get("did_private_key_path"),
            })
        elif name == "anp.fetchDoc":
            result = await fetch_doc_tool.execute(arguments)
        elif name == "anp.invokeOpenRPC":
            result = await invoke_openrpc_tool.execute(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        # 将结果转换为字符串格式返回
        import json
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
        import json
        return [TextContent(type="text", text=json.dumps(error_result, indent=2, ensure_ascii=False))]


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
    """运行 MCP2ANP 桥接服务器。"""
    setup_logging(log_level)

    if reload:
        logger.info("Starting MCP2ANP server with hot reload enabled")
    else:
        logger.info("Starting MCP2ANP server")

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main()
