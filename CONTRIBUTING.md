# 贡献指南

感谢你帮助改进 MCP ↔ ANP 桥接服务！本文记录本地开发、质量控制与提交流程，确保协作顺畅。

## 环境准备

1. 创建虚拟环境并安装开发依赖：
   ```bash
   uv venv --python 3.11
   uv sync --group dev
   pre-commit install
   ```
   若更偏好临时隔离环境，可用 `uvx` 直接运行命令，例如：
   ```bash
   uvx --from . python -m mcp2anp.server --log-level INFO
   uvx --from . pytest --maxfail=1
   ```
2. 配置必要环境变量，例如：
   ```bash
   export ANP_DID_DOCUMENT_PATH="docs/did_public/public-did-doc.json"
   export ANP_DID_PRIVATE_KEY_PATH="docs/did_public/public-private-key.pem"
   export ANP_RPC_ENDPOINT="https://example.com/rpc"
   ```
3. 运行示例客户端验证环境：
   ```bash
   uv run python examples/mcp_client_demo.py
   ```

## 分支与提交

- 分支命名：`feature/<描述>`、`fix/<问题号>`、`chore/<范围>` 等。
- 提交信息：动词开头，≤72 个字符；必要时在正文列出要点。
- 关联问题：使用 `Fixes:` 或 `Refs:`；破坏性变更加 `BREAKING CHANGE:`。

## 代码规范

- 遵循 Google Python Style，公共函数/类补齐类型注解。
- 命名：类 `CamelCase`，函数/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`。
- 通过 `logging` 输出上下文信息（请求 ID、端点等），避免使用 `print`。
- 新模块放入 `mcp2anp/adapters`、`mcp2anp/tools`、`mcp2anp/common` 等既有边界；测试放在 `tests/` 对应路径。
- 复用 `tests/fixtures/` 中的 JSON-RPC 载荷，避免重复硬编码。

## 质量检查

提交前请至少运行：

```bash
uv run ruff mcp2anp tests
uv run black --check mcp2anp tests
uv run pytest --maxfail=1
```

- 覆盖率目标 ≥ 90%。
- 每个适配器/工具需覆盖成功路径、失败场景和边界条件。
- 若修复缺陷，新增回归测试。

## 文档维护

- README 保持用户视角的“使用指南”角色；开发细节写入本文件或 `docs/`。
- 深度协议/架构说明更新 `docs/`（如 `docs/server_remote.md`、`spec.md`）。
- 若新增开发流程，请同步在 README 的“参与贡献”段落添加指引。

## Pull Request 要求

PR 描述请包含：

- 核心变更点（项目符号列出）。
- 验证清单：`uv run pytest`、lint、手动验证等。
- 用户可见变化的截图或日志摘录。
- 潜在风险、兼容性影响或后续事项。

## 依赖与版本

- 更新依赖时同步提交 `uv.lock`、`uv.toml`。
- 使用 `uv pip list --outdated` 追踪升级；若有安全风险，PR 中说明。

## 安全注意事项

- 不要提交真实密钥、私钥或 API Token；使用环境变量或 `.env`。
- 如发现敏感信息泄露，立即通知维护者并轮换相关凭证。

欢迎通过 Issue 或 PR 提出改进建议，我们期待你的贡献！
