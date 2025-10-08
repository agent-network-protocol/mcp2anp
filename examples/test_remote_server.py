"""测试远程 MCP 服务器。

此脚本用于测试远程 MCP 服务器的基本功能。
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp2anp.server_remote import run_http_server


async def main():
    """启动远程服务器进行测试。"""
    print("启动远程 MCP 服务器...")
    print("服务器地址: http://localhost:9880")
    print("按 Ctrl+C 停止服务器")
    print()

    await run_http_server(host="0.0.0.0", port=9880)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务器已停止")
