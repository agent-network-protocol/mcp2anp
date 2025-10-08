#!/usr/bin/env python3
"""测试远程 MCP 服务器功能的脚本。"""

import asyncio
import json

import httpx


async def test_remote_server():
    """测试远程 MCP 服务器的功能。"""
    base_url = "http://127.0.0.1:9880"

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("测试 1: 初始化会话")
        print("=" * 60)

        # 初始化会话
        init_response = await client.post(
            f"{base_url}/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "test-client",
                        "version": "1.0.0"
                    }
                }
            }
        )

        print(f"状态码: {init_response.status_code}")
        print(f"响应: {json.dumps(init_response.json(), indent=2, ensure_ascii=False)}")

        # 提取会话 ID
        session_id = init_response.headers.get("X-MCP-Session-Id")
        if not session_id:
            print("\n❌ 未能获取会话 ID")
            return

        print(f"\n✅ 会话 ID: {session_id}")

        print("\n" + "=" * 60)
        print("测试 2: 获取工具列表")
        print("=" * 60)

        # 获取工具列表
        tools_response = await client.post(
            f"{base_url}/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "X-MCP-Session-Id": session_id
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
        )

        print(f"状态码: {tools_response.status_code}")
        tools_result = tools_response.json()
        print(f"响应: {json.dumps(tools_result, indent=2, ensure_ascii=False)}")

        if "result" in tools_result and "tools" in tools_result["result"]:
            tools = tools_result["result"]["tools"]
            print(f"\n✅ 找到 {len(tools)} 个工具:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")

        print("\n" + "=" * 60)
        print("测试 3: 调用 anp_fetchDoc 工具")
        print("=" * 60)

        # 调用 anp_fetchDoc 工具
        fetch_response = await client.post(
            f"{base_url}/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "X-MCP-Session-Id": session_id
            },
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "anp_fetchDoc",
                    "arguments": {
                        "url": "https://agent-navigation.com/ad.json"
                    }
                }
            }
        )

        print(f"状态码: {fetch_response.status_code}")
        fetch_result = fetch_response.json()
        print(f"响应: {json.dumps(fetch_result, indent=2, ensure_ascii=False)[:1000]}...")

        if "result" in fetch_result:
            print("\n✅ anp_fetchDoc 调用成功")
        else:
            print("\n❌ anp_fetchDoc 调用失败")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_remote_server())
