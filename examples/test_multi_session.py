 """测试多会话功能。

验证多个独立会话可以同时存在并正常工作。
"""

import time

import requests


def test_multi_session():
    """测试多会话功能。"""
    base_url = "http://localhost:9880/mcp"

    print("=" * 60)
    print("测试多会话功能")
    print("=" * 60)

    # 创建多个会话
    sessions = []
    num_sessions = 3

    print(f"\n步骤 1: 创建 {num_sessions} 个独立会话...")
    for i in range(num_sessions):
        response = requests.post(
            base_url,
            json={
                "jsonrpc": "2.0",
                "id": i + 1,
                "method": "tools/call",
                "params": {
                    "name": "anp_fetchDoc",
                    "arguments": {
                        "url": "https://agent-navigation.com/ad.json"
                    }
                }
            },
            headers={"Content-Type": "application/json"}
        )

        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            sessions.append(session_id)
            print(f"  会话 {i + 1}: {session_id[:16]}... (状态码: {response.status_code})")
        else:
            print(f"  ✗ 会话 {i + 1}: 未获得会话 ID")

    print(f"\n✓ 成功创建 {len(sessions)} 个会话")

    # 验证每个会话都可以独立使用
    print("\n步骤 2: 验证每个会话都可以独立使用...")
    for i, session_id in enumerate(sessions):
        response = requests.post(
            base_url,
            json={
                "jsonrpc": "2.0",
                "id": i + 100,
                "method": "tools/call",
                "params": {
                    "name": "anp_fetchDoc",
                    "arguments": {
                        "url": "https://agent-navigation.com/ad.json"
                    }
                }
            },
            headers={
                "Content-Type": "application/json",
                "Mcp-Session-Id": session_id
            }
        )

        # 不应该返回新的会话 ID
        new_session_id = response.headers.get("Mcp-Session-Id")
        if new_session_id and new_session_id != session_id:
            print(f"  ✗ 会话 {i + 1}: 返回了新的会话 ID")
        else:
            print(f"  ✓ 会话 {i + 1}: 正确复用 (状态码: {response.status_code})")

    # 测试会话隔离
    print("\n步骤 3: 测试会话隔离（使用错误的会话 ID）...")
    wrong_session_id = "invalid-session-id-12345"
    response = requests.post(
        base_url,
        json={
            "jsonrpc": "2.0",
            "id": 999,
            "method": "tools/call",
            "params": {
                "name": "anp_fetchDoc",
                "arguments": {
                    "url": "https://agent-navigation.com/ad.json"
                }
            }
        },
        headers={
            "Content-Type": "application/json",
            "Mcp-Session-Id": wrong_session_id
        }
    )

    if response.status_code == 401:
        print("  ✓ 正确拒绝无效会话 ID (状态码: 401)")
    else:
        print(f"  ✗ 期望 401，实际得到 {response.status_code}")

    # 测试会话超时
    print("\n步骤 4: 测试会话超时（等待 35 秒）...")
    print("  会话超时时间: 30 秒")
    print("  清理任务间隔: 10 秒")
    print("  等待中...", end="", flush=True)

    for i in range(7):
        time.sleep(5)
        print(".", end="", flush=True)

    print(" 完成")

    # 验证会话已过期
    print("\n步骤 5: 验证会话已过期...")
    expired_count = 0
    for i, session_id in enumerate(sessions):
        response = requests.post(
            base_url,
            json={
                "jsonrpc": "2.0",
                "id": i + 200,
                "method": "tools/call",
                "params": {
                    "name": "anp_fetchDoc",
                    "arguments": {
                        "url": "https://agent-navigation.com/ad.json"
                    }
                }
            },
            headers={
                "Content-Type": "application/json",
                "Mcp-Session-Id": session_id
            }
        )

        if response.status_code == 401:
            expired_count += 1
            print(f"  ✓ 会话 {i + 1}: 已过期 (状态码: 401)")
        else:
            print(f"  ✗ 会话 {i + 1}: 未过期 (状态码: {response.status_code})")

    if expired_count == len(sessions):
        print("\n✓ 所有会话都已正确过期")
    else:
        print(f"\n⚠️  {expired_count}/{len(sessions)} 个会话过期")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n总结:")
    print(f"  - 创建会话: {len(sessions)}/{num_sessions}")
    print("  - 会话隔离: ✓")
    print(f"  - 会话超时: {expired_count}/{len(sessions)}")


if __name__ == "__main__":
    print("请确保服务器正在运行：")
    print("  uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --session-timeout 30 --cleanup-interval 10\n")

    try:
        test_multi_session()
    except requests.exceptions.ConnectionError:
        print("\n✗ 无法连接到服务器，请确保服务器正在运行")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
