#!/usr/bin/env python3
"""简单的远程 MCP 服务器测试脚本。"""

import json

import requests


def test_remote_server():
    """测试远程 MCP 服务器的功能。"""
    base_url = "http://127.0.0.1:9880"

    print("=" * 60)
    print("测试 1: 检查服务器是否运行")
    print("=" * 60)

    try:
        # 检查服务器是否响应
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"根路径状态码: {response.status_code}")
        print(f"根路径响应: {response.text[:200]}")
    except Exception as e:
        print(f"❌ 服务器未响应: {e}")
        return

    print("\n" + "=" * 60)
    print("测试 2: 尝试 MCP 初始化")
    print("=" * 60)

    try:
        # 尝试初始化会话
        init_response = requests.post(
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
            },
            timeout=10
        )

        print(f"初始化状态码: {init_response.status_code}")
        print(f"初始化响应: {json.dumps(init_response.json(), indent=2, ensure_ascii=False)}")

        # 检查会话 ID
        session_id = init_response.headers.get("X-MCP-Session-Id")
        if session_id:
            print(f"\n✅ 会话 ID: {session_id}")
        else:
            print("\n⚠️  未找到会话 ID")

    except Exception as e:
        print(f"❌ 初始化失败: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_remote_server()
