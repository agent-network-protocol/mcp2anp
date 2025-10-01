#!/usr/bin/env python3
"""
MCP 客户端 Demo

这个脚本演示如何使用 MCP 官方 SDK 创建客户端来调用 mcp2anp 服务器。
它使用 MCP SDK 的 stdio_client 启动服务器并通过 stdio 进行通信。
"""

import asyncio
import json
import logging
import sys

import structlog
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = structlog.get_logger(__name__)


async def demo_basic_usage():
    """演示基本用法"""
    print("=== MCP 客户端基本用法演示 ===")

    # 配置 MCP 服务器参数
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"],
        env=None
    )

    # 使用 MCP SDK 的 stdio_client 连接服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 获取工具列表
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"\n可用工具数量: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description or '无描述'}")

            # 演示调用 anp.fetchDoc 工具（测试本地 ANP 服务器）
            print("\n=== 演示调用 anp.fetchDoc 工具 ===")
            test_url = "http://localhost:8000/agents/travel/test/ad.json"
            print(f"测试 URL: {test_url}")
            try:
                result = await session.call_tool(
                    "anp.fetchDoc",
                    arguments={"url": test_url}
                )
                print("\nfetchDoc 结果:")
                for content in result.content:
                    content_dict = content.model_dump()
                    if content_dict.get('type') == 'text':
                        # 尝试解析并美化 JSON 响应
                        try:
                            text_data = json.loads(content_dict.get('text', '{}'))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(content_dict.get('text'))
            except Exception as e:
                print(f"调用 fetchDoc 失败: {e}")
                print("提示: 请确保本地 ANP 服务器正在运行 (http://localhost:8000)")


async def demo_with_auth():
    """演示带认证的使用（使用真实的 DID 文档）"""
    print("\n=== MCP 客户端认证演示 ===")
    print("注意: 此演示需要 DID 私钥文件，如果没有私钥将无法完成认证")

    # 配置 MCP 服务器参数
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"],
        env=None
    )

    # 使用 MCP SDK 的 stdio_client 连接服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 使用真实的 DID 文档（但没有私钥，仅演示流程）
            print("\n尝试加载 DID 文档: docs/did_public/public-did-doc.json")
            print("(注意: 私钥文件不存在，此步骤将失败，这是预期的)")

            try:
                auth_result = await session.call_tool(
                    "anp.setAuth",
                    arguments={
                        "did_document_path": "docs/did_public/public-did-doc.json",
                        "did_private_key_path": "docs/did_public/private-key.pem"
                    }
                )

                print("\n认证结果:")
                for content in auth_result.content:
                    content_dict = content.model_dump()
                    if content_dict.get('type') == 'text':
                        try:
                            text_data = json.loads(content_dict.get('text', '{}'))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                        except json.JSONDecodeError:
                            print(content_dict.get('text'))

                # 如果认证成功，可以调用需要认证的工具
                if any(hasattr(c, 'text') and '"ok": true' in c.text for c in auth_result.content):
                    print("\n✅ 认证成功！调用需要认证的 OpenRPC 端点...")
                    rpc_result = await session.call_tool(
                        "anp.invokeOpenRPC",
                        arguments={
                            "endpoint": "http://localhost:8000/api/rpc",
                            "method": "getInfo",
                            "params": {}
                        }
                    )
                    print("\nOpenRPC 结果:")
                    for content in rpc_result.content:
                        content_dict = content.model_dump()
                        if content_dict.get('type') == 'text':
                            try:
                                text_data = json.loads(content_dict.get('text', '{}'))
                                print(json.dumps(text_data, indent=2, ensure_ascii=False))
                            except json.JSONDecodeError:
                                print(content_dict.get('text'))
                else:
                    print("\n❌ 认证失败（预期的，因为缺少私钥文件）")

            except Exception as e:
                print(f"\n❌ 认证过程出错: {e}")
                print("提示: 这是预期的，因为私钥文件不存在")


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
            structlog.dev.ConsoleRenderer()
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

        # 认证演示
        await demo_with_auth()

        print("\n=== 演示完成 ===")
        print("要在实际项目中使用，你可以:")
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
