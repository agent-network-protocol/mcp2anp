#!/usr/bin/env python3
"""
测试与本地 ANP 服务器的集成

这个脚本演示如何使用 MCP2ANP 服务器访问 ANP 网络。
服务器会自动使用默认的公共 DID 凭证或环境变量中配置的凭证。
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_anp_server():
    """测试 ANP 服务器功能"""
    print("=== 测试本地 ANP 服务器集成 ===\n")

    # 配置 MCP 服务器参数
    # 服务器会自动使用默认的 DID 凭证或环境变量中的凭证
    # 获取项目根目录
    project_root = Path(__file__).parent.parent

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"],
        env={
            "ANP_DID_DOCUMENT_PATH": str(project_root / "docs" / "did_public" / "public-did-doc.json"),
            "ANP_DID_PRIVATE_KEY_PATH": str(project_root / "docs" / "did_public" / "public-private-key.pem")
        }
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 步骤 1: 获取 ANP 入口文档
            print("步骤 1: 获取 ANP 网络入口文档")
            entry_url = "https://agent-navigation.com/ad.json"
            print(f"URL: {entry_url}\n")

            result = await session.call_tool(
                "anp.fetchDoc",
                arguments={"url": entry_url}
            )

            agent_description = None
            for content in result.content:
                if hasattr(content, 'text'):
                    try:
                        data = json.loads(content.text)
                        if data.get('ok'):
                            print("✅ 成功获取入口文档！")
                            print(json.dumps(data, indent=2, ensure_ascii=False))
                            agent_description = data.get('json', {})
                        else:
                            print(f"❌ 获取失败: {data.get('error', {}).get('code')}")
                            print(f"   消息: {data.get('error', {}).get('message')}\n")
                    except json.JSONDecodeError:
                        print(content.text)

            print("\n" + "="*60 + "\n")

            # 步骤 2: 如果成功获取入口文档，获取第一个智能体的详细信息
            if agent_description and agent_description.get('mainAgentList'):
                first_agent = agent_description['mainAgentList'][0]
                agent_url = first_agent.get('url')

                print("步骤 2: 获取智能体详细信息")
                print(f"智能体: {first_agent.get('name')}")
                print(f"URL: {agent_url}\n")

                agent_result = await session.call_tool(
                    "anp.fetchDoc",
                    arguments={"url": agent_url}
                )

                agent_detail = None
                for content in agent_result.content:
                    if hasattr(content, 'text'):
                        try:
                            data = json.loads(content.text)
                            if data.get('ok'):
                                print("✅ 成功获取智能体详情！")
                                print(json.dumps(data, indent=2, ensure_ascii=False))
                                agent_detail = data.get('json', {})
                            else:
                                print(f"❌ 获取失败: {data.get('error', {}).get('code')}")
                                print(f"   消息: {data.get('error', {}).get('message')}")
                        except json.JSONDecodeError:
                            print(content.text)

                print("\n" + "="*60 + "\n")

                # 步骤 3: 如果智能体有 OpenRPC 接口，尝试调用
                if agent_detail:
                    # 从 interfaces 中查找 OpenRPC 接口
                    openrpc_interface = None
                    interfaces = agent_detail.get('interfaces', [])
                    for interface in interfaces:
                        if interface.get('protocol') == 'openrpc':
                            openrpc_interface = interface
                            break

                    if openrpc_interface:
                        interface_url = openrpc_interface.get('url')
                        print("步骤 3: 获取 OpenRPC 接口定义")
                        print(f"接口: {openrpc_interface.get('description', 'N/A')}")
                        print(f"URL: {interface_url}\n")

                        # 获取接口定义
                        interface_result = await session.call_tool(
                            "anp.fetchDoc",
                            arguments={"url": interface_url}
                        )

                        interface_def = None
                        for content in interface_result.content:
                            if hasattr(content, 'text'):
                                try:
                                    data = json.loads(content.text)
                                    if data.get('ok'):
                                        print("✅ 成功获取 OpenRPC 接口定义！")
                                        # 只打印部分内容，因为接口定义可能很长
                                        interface_def = data.get('json', {})
                                        print(f"OpenRPC 版本: {interface_def.get('openrpc')}")
                                        print(f"服务名称: {interface_def.get('info', {}).get('title')}")
                                        methods = interface_def.get('methods', [])
                                        print(f"可用方法数量: {len(methods)}")
                                        if methods:
                                            print("\n前 3 个方法:")
                                            for method in methods[:3]:
                                                print(f"  - {method.get('name')}: {method.get('summary', 'N/A')}")
                                    else:
                                        print(f"❌ 获取失败: {data.get('error', {}).get('code')}")
                                        print(f"   消息: {data.get('error', {}).get('message')}")
                                except json.JSONDecodeError:
                                    print(content.text)

                        # 步骤 4: 调用 OpenRPC 方法
                        if interface_def:
                            print("\n" + "="*60 + "\n")
                            methods = interface_def.get('methods', [])
                            if methods:
                                first_method = methods[0]
                                method_name = first_method.get('name')

                                # 获取 RPC 端点
                                servers = interface_def.get('servers', [])
                                if servers:
                                    rpc_endpoint = servers[0].get('url')

                                    print("步骤 4: 调用 OpenRPC 方法")
                                    print(f"端点: {rpc_endpoint}")
                                    print(f"方法: {method_name}")
                                    print("参数: 搜索北京的酒店\n")

                                    rpc_call_result = await session.call_tool(
                                        "anp.invokeOpenRPC",
                                        arguments={
                                            "endpoint": rpc_endpoint,
                                            "method": method_name,
                                            "params": {
                                                "city": "北京",
                                                "checkInDate": "2025-11-01",
                                                "checkOutDate": "2025-11-03"
                                            }
                                        }
                                    )

                                    for content in rpc_call_result.content:
                                        if hasattr(content, 'text'):
                                            try:
                                                data = json.loads(content.text)
                                                if data.get('ok'):
                                                    print("✅ 成功调用 OpenRPC 方法！")
                                                    result = data.get('result', {})
                                                    # 打印结果摘要
                                                    if isinstance(result, dict):
                                                        print(f"结果类型: {type(result).__name__}")
                                                        print(f"结果键数量: {len(result.keys())}")
                                                        print("\n结果预览:")
                                                        print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
                                                    else:
                                                        print(f"结果: {result}")
                                                else:
                                                    print(f"❌ 调用失败: {data.get('error', {}).get('code')}")
                                                    print(f"   消息: {data.get('error', {}).get('message')}")
                                            except json.JSONDecodeError:
                                                print(content.text)
                                else:
                                    print("\n步骤 4: 跳过（接口定义中没有服务器端点）")
                    else:
                        print("步骤 3: 跳过（智能体没有 OpenRPC 接口）")
                else:
                    print("步骤 3: 跳过（未能获取智能体详情）")
            else:
                print("步骤 2: 跳过（入口文档中没有智能体列表）")


async def main():
    """主函数"""
    try:
        await test_anp_server()
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

