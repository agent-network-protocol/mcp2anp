# CLAUDE.md

本文件为 Claude Code 在该仓库工作的提示摘要。

## 项目速览

- **定位**：MCP ↔ ANP 桥接服务，让支持 MCP 的客户端（Claude Desktop、Cursor 等）能够访问 ANP 网络。
- **工具集**：仅暴露 `anp.fetchDoc` 与 `anp.invokeOpenRPC` 两个工具；DID 凭证在服务器启动时通过环境变量加载（或退回到 `docs/did_public/` 的公共凭证）。
- **代码结构**：
  - `mcp2anp/server.py`：stdio 传输模式的 MCP 服务器。
  - `mcp2anp/server_remote.py`：FastMCP HTTP 传输实现，依靠 `ServerSession` 管理会话。
  - `mcp2anp/core/handlers.py`：`ANPHandler` 封装工具逻辑。
  - `mcp2anp/utils/`：日志、Pydantic 模型等通用工具。
  - `docs/`：最新的架构、远程部署、会话与鉴权文档。

## 常用命令

```bash
# 安装依赖（需先 uv venv --python 3.11）
uv sync

# 启动本地 stdio 服务器
uv run python -m mcp2anp.server --log-level INFO

# 启动远程 HTTP 服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 运行官方示例
uv run python examples/mcp_client_demo.py

# 运行测试
uv run pytest
```

## 约定与注意事项

- 认证通过环境变量控制：`ANP_DID_DOCUMENT_PATH` 与 `ANP_DID_PRIVATE_KEY_PATH`；未提供时使用公共凭证。
- 远程模式的访问控制需通过 `set_auth_callback()` 自定义回调实现（详见 `docs/REMOTE_SERVER.md` 与 `AUTH_EXAMPLE.md`）。
- 会话隔离依赖 FastMCP 的 `ServerSession`，状态存储在 `SESSION_STORE`（`WeakKeyDictionary`）；无需手写 SessionManager。
- 日志使用 `structlog`；保持新日志字段与现有格式一致。
- 文档采用 Google Python 风格、注释与日志使用英文。

## 推荐阅读顺序

1. `README.md` – 项目背景、快速开始。
2. `docs/usage.md` – 工具调用方式与最佳实践。
3. `docs/REMOTE_SERVER.md` – 远程部署、鉴权示例与运维建议。
4. `docs/STATEFUL_SESSION.md` – 会话模型与调试技巧。
5. `spec.md` – 更详细的设计说明。

协作时请优先维护上述文档的准确性，与代码变更保持同步。
