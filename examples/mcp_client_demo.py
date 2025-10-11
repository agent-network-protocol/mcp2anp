#!/usr/bin/env python3
"""
MCP 客户端 Demo

这个脚本演示如何使用 MCP 官方 SDK 创建客户端来调用 mcp2anp 服务器。
它使用 MCP SDK 的 stdio_client 启动服务器并通过 stdio 进行通信。
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = structlog.get_logger(__name__)

# Configuration: ANP service domain
ANP_DOMAIN = "https://agent-connect.ai"

# Configure DID credentials using absolute paths
project_root = Path(__file__).parent.parent
os.environ["ANP_DID_DOCUMENT_PATH"] = str(
    project_root / "docs" / "did_public" / "public-did-doc.json"
)
os.environ["ANP_DID_PRIVATE_KEY_PATH"] = str(
    project_root / "docs" / "did_public" / "public-private-key.pem"
)


async def demo_basic_usage():
    """演示基本用法"""
    print("=== MCP 客户端基本用法演示 ===")
    print("注意: DID 认证通过环境变量配置，或使用默认凭证\n")

    # 配置 MCP 服务器参数
    server_params = StdioServerParameters(
        command="uv", args=["run", "python", "-m", "mcp2anp.server"], env=None
    )

    # 使用 MCP SDK 的 stdio_client 连接服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 获取工具列表
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"可用工具数量: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description or '无描述'}")

            # 演示调用 anp.fetchDoc 工具（测试本地 ANP 服务器）
            print("\n=== 演示调用 anp.fetchDoc 工具 ===")
            test_url = f"{ANP_DOMAIN}/agents/test/ad.json"
            print(f"测试 URL: {test_url}")
            try:
                result = await session.call_tool(
                    "anp.fetchDoc", arguments={"url": test_url}
                )
                print("\nfetchDoc 结果:")
                for content in result.content:
                    content_dict = content.model_dump()
                    if content_dict.get("type") == "text":
                        # 尝试解析并美化 JSON 响应
                        try:
                            text_data = json.loads(content_dict.get("text", "{}"))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(content_dict.get("text"))
            except Exception as e:
                print(f"调用 fetchDoc 失败: {e}")
                print(f"提示: 请确保本地 ANP 服务器正在运行 (ANP_DOMAIN: {ANP_DOMAIN})")

            # 演示调用 anp.invokeOpenRPC 工具（测试 echo 方法）
            print("\n=== 演示调用 anp.invokeOpenRPC 工具 (echo 方法) ===")
            test_message = "Hello from MCP client!"
            jsonrpc_endpoint = f"{ANP_DOMAIN}/agents/test/jsonrpc"
            print(f"测试消息: {test_message}")
            print(f"JSON-RPC 端点: {jsonrpc_endpoint}")
            try:
                rpc_result = await session.call_tool(
                    "anp.invokeOpenRPC",
                    arguments={
                        "endpoint": jsonrpc_endpoint,
                        "method": "echo",
                        "params": {"message": test_message},
                    },
                )
                print("\necho 方法调用结果:")
                for content in rpc_result.content:
                    content_dict = content.model_dump()
                    if content_dict.get("type") == "text":
                        try:
                            text_data = json.loads(content_dict.get("text", "{}"))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(content_dict.get("text"))
            except Exception as e:
                print(f"调用 echo 方法失败: {e}")
                print(f"提示: 请确保本地 ANP 服务器正在运行 (ANP_DOMAIN: {ANP_DOMAIN})")

            # 演示调用 anp.invokeOpenRPC 工具（测试 getStatus 方法）
            print("\n=== 演示调用 anp.invokeOpenRPC 工具 (getStatus 方法) ===")
            print(f"JSON-RPC 端点: {jsonrpc_endpoint}")
            try:
                status_result = await session.call_tool(
                    "anp.invokeOpenRPC",
                    arguments={
                        "endpoint": jsonrpc_endpoint,
                        "method": "getStatus",
                        "params": {},
                    },
                )
                print("\ngetStatus 方法调用结果:")
                for content in status_result.content:
                    content_dict = content.model_dump()
                    if content_dict.get("type") == "text":
                        try:
                            text_data = json.loads(content_dict.get("text", "{}"))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(content_dict.get("text"))
            except Exception as e:
                print(f"调用 getStatus 方法失败: {e}")
                print(f"提示: 请确保本地 ANP 服务器正在运行 (ANP_DOMAIN: {ANP_DOMAIN})")


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    print("MCP2ANP 客户端演示 (使用官方 MCP SDK)")
    print("==========================================")

    try:
        # 基本用法演示
        await demo_basic_usage()

        print("\n=== 演示完成 ===")
        print("演示内容包括:")
        print("- anp.fetchDoc: 获取智能体描述文档")
        print("- anp.invokeOpenRPC(echo): 调用回显方法测试连接")
        print("- anp.invokeOpenRPC(getStatus): 获取智能体状态信息")
        print("\n环境变量配置:")
        print("- ANP_DID_DOCUMENT_PATH: 自定义 DID 文档路径")
        print("- ANP_DID_PRIVATE_KEY_PATH: 自定义 DID 私钥路径")
        print("（未设置时使用默认凭证）")
        print("\n要在实际项目中使用，你可以:")
        print("1. 导入 MCP SDK: from mcp import ClientSession, StdioServerParameters")
        print("2. 导入 stdio_client: from mcp.client.stdio import stdio_client")
        print("3. 配置服务器参数: server_params = StdioServerParameters(...)")
        print("4. 使用 async with stdio_client(server_params) 创建连接")
        print("5. 使用 async with ClientSession(read, write) 创建会话")
        print("6. 调用 session.initialize() 初始化")
        print("7. 使用 session.list_tools() 获取工具列表")
        print("8. 使用 session.call_tool(name, arguments) 调用工具")

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        logger.error("主程序执行失败", error=str(e))
        print(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
