# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个 MCP-to-ANP 桥接器项目，将 ANP (Agent Network Protocol) 协议转换为 MCP (Model Control Protocol) 工具，让支持 MCP 的应用（如 Claude Desktop、Cursor）能够访问 ANP 智能体。

## 核心架构

项目直接使用agent-connect库，通过3个MCP工具实现协议转换：
- `anp.setAuth`: 设置 DID 认证上下文（使用本地 DID 文档和私钥文件）
- `anp.fetchDoc`: 抓取并解析 ANP 文档，提取可跟进的链接（使用ANPCrawler）
- `anp.invokeOpenRPC`: 调用 OpenRPC 端点（JSON-RPC 2.0，通过ANPCrawler）

**重要：** 项目已移除自定义的adapters/和auth/模块，直接使用agent-connect库的ANPCrawler和DIDWbaAuthHeader进行ANP协议交互和DID认证。

项目简化后结构：
- `mcp2anp/`: 运行时代码
  - `server.py`: MCP服务器主入口，直接集成3个工具和agent-connect库
  - `utils/`: 工具和模型（`models.py`, `logging.py`）
- `docs/did_public/`: DID认证凭证
  - `public-did-doc.json`: 公共DID文档
  - `public-private-key.pem`: 公共DID私钥
- `examples/`: 测试和示例代码（替代传统的tests/目录）
- `docs/`: 架构文档
- `spec.md`: 详细的技术实现文档
- `run_tests.sh`: 交互式测试脚本

## 开发命令

```bash
# 环境管理
uv venv --python 3.11    # 创建Python 3.11虚拟环境
uv sync                   # 安装依赖并更新uv.lock
uv sync --group dev       # 安装开发依赖（包含测试工具）

# 开发运行
uv run python -m mcp2anp.server --reload --log-level DEBUG    # 本地运行带热重载和调试日志
uv run mcp2anp --log-level INFO                               # 生产模式运行

# 测试 - 项目使用交互式测试脚本而非传统pytest
./run_tests.sh           # 交互式测试菜单（快速测试、完整示例、单独工具测试等）
uv run python examples/test_example.py                       # 运行完整示例测试
uv run python examples/test_individual_tools.py              # 单独工具测试

# 代码质量
uv run black mcp2anp/ examples/     # 格式化代码
uv run ruff mcp2anp/ examples/      # 代码检查
```

## 编码规范

- 遵循Google Python编程规范
- 类使用`CamelCase`，函数和变量使用`snake_case`，常量使用`UPPER_SNAKE_CASE`
- 使用显式类型提示
- 通过`logging`模块记录日志，使用英文和可追踪的上下文信息
- 测试覆盖率目标≥90%

## 安全要求

- DID私钥等敏感信息不得提交到仓库
- 敏感配置通过环境变量加载（如`ANP_RPC_ENDPOINT`）
- 在`docs/examples/`中仅提供脱敏的示例配置

## 测试策略

- 项目采用交互式测试，而非传统的pytest单元测试
- 测试代码位于`examples/`目录中：
  - `test_example.py`: 完整的工作流示例测试
  - `test_individual_tools.py`: 单独工具功能测试
  - `test_with_local_server.py`: 本地服务器连接测试
- 使用`./run_tests.sh`脚本提供菜单式测试选项
- 测试涵盖成功、失败和边界情况
- 支持与agent-connect.ai示例进行集成测试

## 关键入口文件

- `mcp2anp/server.py:28-100`: MCP工具定义和JSON Schema
- `mcp2anp/server.py:104-130`: 工具调用分发逻辑
- `mcp2anp/server.py:133-165`: setAuth工具处理（创建ANPCrawler实例）
- `mcp2anp/server.py:168-222`: fetchDoc工具处理（使用ANPCrawler.fetch_text）
- `mcp2anp/server.py:225-280`: invokeOpenRPC工具处理（使用ANPCrawler.execute_tool_call）
- `mcp2anp/server.py:305-323`: CLI主入口和热重载支持

## DID认证说明

项目使用`docs/did_public/`中的公共DID凭证作为默认认证：
- 无需setAuth时：自动使用`docs/did_public/public-did-doc.json`和`public-private-key.pem`
- 调用setAuth后：使用用户指定的DID凭证
- 所有ANP请求都通过agent-connect库的DID认证机制进行
