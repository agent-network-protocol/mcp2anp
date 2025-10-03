#!/usr/bin/env python3
"""测试 MCP 工具功能的脚本。"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_tools():
    """测试 MCP 工具功能。"""
    print("=" * 60)
    print("测试 MCP 工具功能")
    print("=" * 60)

    # 使用 stdio 传输测试本地服务器
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            init_result = await session.initialize(
                protocol_version="2024-11-05",
                capabilities={},
                client_info={"name": "test-client", "version": "1.0.0"}
            )
            print(f"✅ 初始化成功: {init_result.server_info}")

            # 获取工具列表
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"\n✅ 找到 {len(tools)} 个工具:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")

            # 测试 anp_fetchDoc 工具
            print("\n" + "=" * 60)
            print("测试 anp_fetchDoc 工具")
            print("=" * 60)

            try:
                fetch_result = await session.call_tool(
                    "anp_fetchDoc",
                    {"url": "https://agent-navigation.com/ad.json"}
                )
                print(f"✅ anp_fetchDoc 调用成功")
                print(f"结果长度: {len(fetch_result.content[0].text)} 字符")
                print(f"结果预览: {fetch_result.content[0].text[:500]}...")
            except Exception as e:
                print(f"❌ anp_fetchDoc 调用失败: {e}")

            # 测试 anp_invokeOpenRPC 工具
            print("\n" + "=" * 60)
            print("测试 anp_invokeOpenRPC 工具")
            print("=" * 60)

            try:
                # 这里需要一个有效的 OpenRPC 端点来测试
                print("⚠️  需要有效的 OpenRPC 端点来测试 anp_invokeOpenRPC")
                print("   可以使用示例端点进行测试")
            except Exception as e:
                print(f"❌ anp_invokeOpenRPC 调用失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tools())
