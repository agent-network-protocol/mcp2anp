"""共享的工具处理函数。"""

import os
from pathlib import Path
from typing import Any

import structlog
from agent_connect.anp_crawler.anp_crawler import ANPCrawler

from ..utils import models

logger = structlog.get_logger(__name__)


class ANPHandler:
    """ANP 工具处理类。"""

    def __init__(self, anp_crawler: ANPCrawler | None = None):
        self.anp_crawler = anp_crawler

    async def handle_fetch_doc(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """处理 fetchDoc 工具调用。"""
        try:
            # 验证参数
            request = models.FetchDocRequest(**arguments)

            logger.info("Fetching document", url=request.url)

            # 检查 ANPCrawler 是否已初始化
            if self.anp_crawler is None:
                return {
                    "ok": False,
                    "error": {
                        "code": "ANP_NOT_INITIALIZED",
                        "message": "ANPCrawler not initialized. Please check DID credentials.",
                    },
                }

            # 使用 ANPCrawler 获取文档
            content_result, interfaces = await self.anp_crawler.fetch_text(request.url)

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
                # "interfaces": links,
            }

            # 如果内容是 JSON，尝试解析
            # try:
            #     if content_result.get("content"):
            #         json_data = json.loads(content_result["content"])
            #         result["json"] = json_data
            # except json.JSONDecodeError:
            #     pass  # 不是 JSON 内容，跳过

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

    async def handle_invoke_openrpc(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """处理 invokeOpenRPC 工具调用。"""
        try:
            # 验证参数
            request = models.InvokeOpenRPCRequest(**arguments)

            logger.info(
                "Invoking OpenRPC method",
                endpoint=request.endpoint,
                method=request.method,
                params=request.params,
            )

            # 检查 ANPCrawler 是否已初始化
            if self.anp_crawler is None:
                logger.error("ANPCrawler not initialized. Please check DID credentials.")
                return {
                    "ok": False,
                    "error": {
                        "code": "ANP_NOT_INITIALIZED",
                        "message": "ANPCrawler not initialized. Please check DID credentials.",
                    },
                }

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

            result = await self.anp_crawler.execute_tool_call(tool_name, tool_params)

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


def initialize_anp_crawler() -> ANPCrawler | None:
    """从环境变量初始化 ANPCrawler。"""
    # 从环境变量读取 DID 凭证路径
    did_document_path = os.environ.get("ANP_DID_DOCUMENT_PATH")
    did_private_key_path = os.environ.get("ANP_DID_PRIVATE_KEY_PATH")

    logger.info(
        "DID credentials from environment variables",
        did_doc=did_document_path,
        private_key=did_private_key_path,
    )

    # 如果环境变量未设置，使用默认的公共 DID 凭证
    if not did_document_path or not did_private_key_path:
        project_root = Path(__file__).parent.parent.parent
        did_document_path = str(project_root / "docs" / "did_public" / "public-did-doc.json")
        did_private_key_path = str(project_root / "docs" / "did_public" / "public-private-key.pem")
        logger.info(
            "Using default DID credentials",
            did_doc=did_document_path,
            private_key=did_private_key_path,
        )
    else:
        logger.info(
            "Using DID credentials from environment variables",
            did_doc=did_document_path,
            private_key=did_private_key_path,
        )

    try:
        # 创建 ANPCrawler 实例
        anp_crawler = ANPCrawler(
            did_document_path=did_document_path,
            private_key_path=did_private_key_path,
            cache_enabled=True
        )
        logger.info("ANPCrawler initialized successfully")
        return anp_crawler
    except Exception as e:
        logger.error("Failed to initialize ANPCrawler", error=str(e))
        return None
