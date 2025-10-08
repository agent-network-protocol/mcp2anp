"""测试有状态会话功能的示例脚本。

这个脚本演示了如何使用 Mcp-Session-Id 进行会话管理。
"""

import json

import requests


def test_stateful_session(session_timeout=60):
    """测试有状态会话功能。

    Args:
        session_timeout: 会话超时时间（秒），用于显示提示信息
    """
    base_url = "http://localhost:9880/mcp"

    print("=" * 60)
    print("测试有状态会话功能（仅超时机制）")
    print("=" * 60)

    # 第一次请求：创建会话
    print("\n1. 首次请求（创建会话）...")
    first_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "anp_fetchDoc",
            "arguments": {
                "url": "https://agent-navigation.com/ad.json"
            }
        }
    }

    response1 = requests.post(
        base_url,
        json=first_request,
        headers={"Content-Type": "application/json"}
    )

    print(f"状态码: {response1.status_code}")
    print(f"响应头: {dict(response1.headers)}")

    # 获取会话 ID
    session_id = response1.headers.get("Mcp-Session-Id")
    if session_id:
        print(f"✓ 获得会话 ID: {session_id}")
    else:
        print("✗ 未获得会话 ID")
        return

    try:
        result1 = response1.json()
        print(f"响应: {json.dumps(result1, indent=2, ensure_ascii=False)[:200]}...")
    except Exception as e:
        print(f"解析响应失败: {e}")
        print(f"原始响应: {response1.text[:500]}")

    # 第二次请求：使用会话 ID
    print(f"\n2. 第二次请求（使用会话 ID: {session_id}）...")
    second_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "anp_fetchDoc",
            "arguments": {
                "url": "https://agent-navigation.com/ad.json"
            }
        }
    }

    response2 = requests.post(
        base_url,
        json=second_request,
        headers={
            "Content-Type": "application/json",
            "Mcp-Session-Id": session_id
        }
    )

    print(f"状态码: {response2.status_code}")
    returned_session_id = response2.headers.get("Mcp-Session-Id")
    if returned_session_id:
        print(f"响应中的会话 ID: {returned_session_id}")
    else:
        print("响应中没有会话 ID（这是正常的，因为是已有会话）")

    try:
        result2 = response2.json()
        print(f"响应: {json.dumps(result2, indent=2, ensure_ascii=False)[:200]}...")
    except Exception as e:
        print(f"解析响应失败: {e}")
        print(f"原始响应: {response2.text[:500]}")

    # 第三次请求：使用无效的会话 ID
    print("\n3. 使用无效的会话 ID...")
    invalid_session_id = "invalid-session-id-12345"

    response3 = requests.post(
        base_url,
        json=second_request,
        headers={
            "Content-Type": "application/json",
            "Mcp-Session-Id": invalid_session_id
        }
    )

    print(f"状态码: {response3.status_code}")
    if response3.status_code == 401:
        print("✓ 正确返回 401 未授权")
        try:
            error_result = response3.json()
            print(f"错误信息: {json.dumps(error_result, indent=2, ensure_ascii=False)}")
        except Exception as e:
            print(f"解析错误响应失败: {e}")
    else:
        print(f"✗ 期望 401，实际得到 {response3.status_code}")

    # 第四次请求：等待会话超时测试（可选，需要较长时间）
    print(f"\n4. 会话超时测试（会话将在 {session_timeout} 秒后过期）...")
    print("   注意：完整测试需要等待超时时间，这里跳过")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    print("请确保服务器正在运行：")
    print("  uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880\n")

    try:
        test_stateful_session()
    except requests.exceptions.ConnectionError:
        print("\n✗ 无法连接到服务器，请确保服务器正在运行")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
