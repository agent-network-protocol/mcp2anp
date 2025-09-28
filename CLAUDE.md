# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个 MCP-to-ANP 桥接器项目，将 ANP (Agent Network Protocol) 协议转换为 MCP (Model Control Protocol) 工具，让支持 MCP 的应用（如 Claude Desktop、Cursor）能够访问 ANP 智能体。

## 核心架构

项目主要通过 3 个 MCP 工具实现协议转换：
- `anp.setAuth`: 设置 DID 认证上下文（使用本地 DID 文档和私钥文件）
- `anp.fetchDoc`: 抓取并解析 ANP 文档，提取可跟进的链接
- `anp.invokeOpenRPC`: 调用 OpenRPC 端点（JSON-RPC 2.0）

项目结构规划：
- `src/mcp2anp/`: 运行时代码，包含适配器、工具处理器和共享工具
- `tests/`: 测试代码，使用 pytest
- `docs/`: 架构文档
- `assets/`: 图表和示例资源

## 开发命令

```bash
# 环境管理
uv venv --python 3.11    # 创建Python 3.11虚拟环境
uv sync                   # 安装依赖并更新uv.lock

# 开发运行
uv run python -m mcp2anp.server --reload    # 本地运行带热重载

# 测试
uv run pytest           # 运行测试
uv run pytest -k pattern --maxfail=1       # 模式过滤测试
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

- 使用pytest和pytest-asyncio
- 为每个工具适配器覆盖成功、失败和边界情况
- 网络调用使用fixtures或本地mock
- 测试文件命名为`test_*.py`