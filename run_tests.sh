#!/bin/bash

# MCP2ANP 测试运行脚本
# 此脚本设置环境并运行各种测试

echo "🚀 MCP2ANP 测试套件"
echo "===================="

# 检查 Python 环境
echo "🐍 检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未找到，请安装 Python 3.11+"
    exit 1
fi

# 检查 uv 环境
echo "📦 检查 uv 包管理器..."
if ! command -v uv &> /dev/null; then
    echo "❌ uv 未找到，请安装 uv"
    echo "💡 安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 切换到项目目录
cd "$(dirname "$0")"

echo "📁 当前目录: $(pwd)"

# 安装依赖
echo "📥 安装依赖..."
uv sync --quiet

if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败"
    echo "💡 尝试手动运行: uv sync"
    exit 1
fi

echo "✅ 依赖安装完成"

# 创建 DID 示例文件（如果不存在）
if [ ! -f "examples/did-example.json" ]; then
    echo "🔑 创建 DID 示例文件..."
    uv run python examples/create_did_example.py
fi

# 运行测试选项
echo ""
echo "选择要运行的测试:"
echo "1) 快速测试 - 验证工具列表和基本功能"
echo "2) 完整示例测试 - 使用 agent-connect.ai 示例"
echo "3) 单独工具测试 - 详细测试每个工具"
echo "4) 启动 MCP 服务器 (用于客户端连接)"
echo "5) 全部运行"

read -p "请选择 (1-5): " choice

case $choice in
    1)
        echo "🏃 运行快速测试..."
        uv run python -c "
import asyncio
import sys
sys.path.insert(0, 'src')
from mcp2anp.server import list_tools

async def quick_test():
    print('测试工具列表...')
    tools = await list_tools()
    print(f'发现 {len(tools)} 个工具:')
    for tool in tools:
        print(f'  - {tool.name}')
    print('✅ 快速测试完成')

asyncio.run(quick_test())
"
        ;;
    2)
        echo "🌐 运行完整示例测试..."
        uv run python examples/test_example.py
        ;;
    3)
        echo "🔧 运行单独工具测试..."
        uv run python examples/test_individual_tools.py
        ;;
    4)
        echo "🖥️  启动 MCP 服务器..."
        echo "💡 使用 Ctrl+C 停止服务器"
        echo "📋 服务器将在 stdio 模式下运行，等待 MCP 客户端连接"
        uv run python -m mcp2anp.server
        ;;
    5)
        echo "🎯 运行全部测试..."
        echo ""
        echo "--- 快速测试 ---"
        uv run python -c "
import asyncio
import sys
sys.path.insert(0, 'src')
from mcp2anp.server import list_tools

async def quick_test():
    print('✅ 测试工具列表...')
    tools = await list_tools()
    print(f'发现 {len(tools)} 个工具: {[t.name for t in tools]}')

asyncio.run(quick_test())
"
        echo ""
        echo "--- 完整示例测试 ---"
        uv run python examples/test_example.py
        echo ""
        echo "--- 单独工具测试 ---"
        uv run python examples/test_individual_tools.py
        ;;
    *)
        echo "❌ 无效选择"
        exit 1
        ;;
esac

echo ""
echo "🏁 测试完成!"
echo ""
echo "📚 更多信息:"
echo "  - 查看 spec.md 了解项目详情"
echo "  - 查看 examples/ 目录了解使用示例"
echo "  - 使用 'uv run python -m mcp2anp.server --help' 查看服务器选项"