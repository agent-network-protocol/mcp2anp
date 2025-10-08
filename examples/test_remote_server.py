"""测试远程 MCP 服务器。

此脚本用于测试远程 MCP 服务器的基本功能。

注意：此文件已废弃。请直接使用以下命令启动服务器：

    uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

或者：

    uv run mcp2anp-remote --host 0.0.0.0 --port 9880
"""

import sys


def main():
    """提示用户使用正确的启动方式。"""
    print("=" * 60)
    print("此测试文件已废弃")
    print("=" * 60)
    print()
    print("请使用以下命令启动远程 MCP 服务器：")
    print()
    print("  uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880")
    print()
    print("或者：")
    print()
    print("  uv run mcp2anp-remote --host 0.0.0.0 --port 9880")
    print()
    print("=" * 60)
    sys.exit(1)


if __name__ == "__main__":
    main()
