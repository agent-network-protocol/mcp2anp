#!/usr/bin/env python3
"""
测试与本地 ANP 服务器的集成

这个脚本演示如何先设置认证，然后调用需要认证的端点。
注意：需要有效的私钥文件才能成功。
"""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_authenticated_flow():
    """测试完整的认证流程"""
    print("=== 测试本地 ANP 服务器集成 ===\n")

    # 配置 MCP 服务器参数
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 步骤 1: 尝试不带认证访问（应该失败）
            print("步骤 1: 尝试不带认证访问受保护的端点")
            test_url = "https://agent-connect.ai/agents/test/ad.json"
            print(f"URL: {test_url}\n")

            result = await session.call_tool(
                "anp.fetchDoc",
                arguments={"url": test_url}
            )

            for content in result.content:
                if hasattr(content, 'text'):
                    try:
                        data = json.loads(content.text)
                        if not data.get('ok'):
                            print(f"❌ 预期的错误: {data.get('error', {}).get('code')}")
                            print(f"   消息: {data.get('error', {}).get('message')}\n")
                    except json.JSONDecodeError:
                        print(content.text)

            # 步骤 2: 设置认证
            print("步骤 2: 设置 DID 认证")
            print("DID 文档: docs/did_public/public-did-doc.json")
            print("注意: 需要对应的私钥文件\n")

            auth_result = await session.call_tool(
                "anp.setAuth",
                arguments={
                    "did_document_path": "docs/did_public/public-did-doc.json",
                    "did_private_key_path": "docs/did_public/private-key.pem"
                }
            )

            auth_success = False
            for content in auth_result.content:
                if hasattr(content, 'text'):
                    try:
                        data = json.loads(content.text)
                        if data.get('ok'):
                            print("✅ 认证成功！\n")
                            auth_success = True
                        else:
                            print(f"❌ 认证失败: {data.get('error', {}).get('code')}")
                            print(f"   消息: {data.get('error', {}).get('message')}")
                            print("   提示: 需要有效的私钥文件 (docs/did_public/private-key.pem)\n")
                    except json.JSONDecodeError:
                        print(content.text)

            # 步骤 3: 如果认证成功，再次尝试访问
            if auth_success:
                print("步骤 3: 使用认证后再次访问端点")
                print(f"URL: {test_url}\n")

                result = await session.call_tool(
                    "anp.fetchDoc",
                    arguments={"url": test_url}
                )

                for content in result.content:
                    if hasattr(content, 'text'):
                        try:
                            data = json.loads(content.text)
                            if data.get('ok'):
                                print("✅ 成功获取文档！")
                                print(json.dumps(data, indent=2, ensure_ascii=False))
                            else:
                                print(f"❌ 获取失败: {data.get('error', {}).get('code')}")
                        except json.JSONDecodeError:
                            print(content.text)
            else:
                print("步骤 3: 跳过（认证失败）")
                print("\n要成功运行此测试，需要:")
                print("1. 确保本地 ANP 服务器运行在 http://localhost:9880")
                print("2. 创建与 DID 文档匹配的私钥文件")
                print("3. 将私钥保存到 docs/did_public/private-key.pem")


async def main():
    """主函数"""
    try:
        await test_authenticated_flow()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

