"""MCP server implementation for ANP bridge."""

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import click
import mcp.server.stdio
import structlog
from agent_connect.anp_crawler.anp_crawler import ANPCrawler
from agent_connect.authentication import DIDWbaAuthHeader
from mcp.server import Server
from mcp.types import TextContent, Tool

from .utils import models, setup_logging

logger = structlog.get_logger(__name__)

# 创建 MCP Server 实例
server = Server("mcp2anp")

# 全局状态：ANPCrawler 实例（初始化时为 None）
anp_crawler: ANPCrawler | None = None


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
    logger.info("Tool called", tool_name=name, args=arguments)

    try:
        if name == "anp.setAuth":
            result = await handle_set_auth(arguments)
        elif name == "anp.fetchDoc":
            result = await handle_fetch_doc(arguments)
        elif name == "anp.invokeOpenRPC":
            result = await handle_invoke_openrpc(arguments)
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


async def handle_set_auth(arguments: dict[str, Any]) -> dict[str, Any]:
    """处理 setAuth 工具调用。"""
    global anp_crawler

    try:
        # 验证参数
        request = models.SetAuthRequest(**arguments)

        logger.info(
            "Setting up authentication",
            did_doc_path=request.did_document_path,
            private_key_path=request.did_private_key_path,
        )

        # 创建新的 ANPCrawler 实例，带认证
        anp_crawler = ANPCrawler(
            did_document_path=request.did_document_path,
            private_key_path=request.did_private_key_path,
            cache_enabled=True
        )

        logger.info("Authentication context set successfully")
        return {"ok": True}

    except Exception as e:
        logger.error("Failed to set authentication", error=str(e))
        return {
            "ok": False,
            "error": {
                "code": "ANP_AUTH_ERROR",
                "message": str(e),
            },
        }


async def handle_fetch_doc(arguments: dict[str, Any]) -> dict[str, Any]:
    """处理 fetchDoc 工具调用。"""
    global anp_crawler

    try:
        # 验证参数
        request = models.FetchDocRequest(**arguments)

        logger.info("Fetching document", url=request.url)

        # 如果没有设置 ANPCrawler，使用公共 DID 凭证创建实例
        if anp_crawler is None:
            # 使用项目提供的公共 DID 凭证
            from pathlib import Path
            project_root = Path(__file__).parent.parent
            default_did_doc = str(project_root / "docs" / "did_public" / "public-did-doc.json")
            default_private_key = str(project_root / "docs" / "did_public" / "public-private-key.pem")

            anp_crawler = ANPCrawler(
                did_document_path=default_did_doc,
                private_key_path=default_private_key,
                cache_enabled=True
            )
            logger.info("Created ANPCrawler with default DID credentials")

        # 使用 ANPCrawler 获取文档
        content_result, interfaces = await anp_crawler.fetch_text(request.url)

        # 构建链接列表
        links = []
        for interface in interfaces:
            func_info = interface.get("function", {})
            links.append({
                "rel": "interface",
                "url": request.url,  # ANPCrawler 已经处理了 URL 解析
                "title": func_info.get("name", ""),
                "description": func_info.get("description", ""),
            })

        result = {
            "ok": True,
            "contentType": content_result.get("content_type", "application/json"),
            "text": content_result.get("content", ""),
            "links": links,
        }

        # 如果内容是 JSON，尝试解析
        try:
            if content_result.get("content"):
                json_data = json.loads(content_result["content"])
                result["json"] = json_data
        except json.JSONDecodeError:
            pass  # 不是 JSON 内容，跳过

        logger.info("Document fetched successfully", url=request.url, links_count=len(links))
        return result

    except Exception as e:
        logger.error("Failed to fetch document", url=arguments.get("url"), error=str(e))
        return {
            "ok": False,
            "error": {
                "code": "ANP_FETCH_ERROR",
                "message": str(e),
            },
        }


async def handle_invoke_openrpc(arguments: dict[str, Any]) -> dict[str, Any]:
    """处理 invokeOpenRPC 工具调用。"""
    global anp_crawler

    try:
        # 验证参数
        request = models.InvokeOpenRPCRequest(**arguments)

        logger.info(
            "Invoking OpenRPC method",
            endpoint=request.endpoint,
            method=request.method,
            params=request.params,
        )

        # 如果没有设置 ANPCrawler，使用公共 DID 凭证创建实例
        if anp_crawler is None:
            # 使用项目提供的公共 DID 凭证
            from pathlib import Path
            project_root = Path(__file__).parent.parent
            default_did_doc = str(project_root / "docs" / "did_public" / "public-did-doc.json")
            default_private_key = str(project_root / "docs" / "did_public" / "public-private-key.pem")

            anp_crawler = ANPCrawler(
                did_document_path=default_did_doc,
                private_key_path=default_private_key,
                cache_enabled=True
            )

        # 构建工具名称（ANPCrawler 需要这种格式）
        tool_name = f"{request.method}"

        # 调用工具
        if request.params is None:
            tool_params = {}
        elif isinstance(request.params, dict):
            tool_params = request.params
        elif isinstance(request.params, list):
            # 如果是列表，转换为字典
            tool_params = {"args": request.params}
        else:
            tool_params = {"value": request.params}

        result = await anp_crawler.execute_tool_call(tool_name, tool_params)

        logger.info("OpenRPC method invoked successfully", method=request.method)
        return {
            "ok": True,
            "result": result,
            "raw": result,  # ANPCrawler 已经返回结构化结果
        }

    except Exception as e:
        logger.error(
            "Failed to invoke OpenRPC method",
            endpoint=arguments.get("endpoint"),
            method=arguments.get("method"),
            error=str(e),
        )
        return {
            "ok": False,
            "error": {
                "code": "ANP_RPC_ERROR",
                "message": str(e),
            },
        }


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