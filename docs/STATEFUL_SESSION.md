# 有状态会话模式说明

`mcp2anp.server_remote` 依托 FastMCP 的 `ServerSession` 能力，为每个客户端连接维护独立的 ANP 上下文。本文档概述当前实现方式及调试要点，替换早期的自定义 SessionManager 方案。

## 架构要点

- 会话状态通过 `WeakKeyDictionary[ServerSession, dict]` 存储在内存中，键值就是 FastMCP 分配的 `ServerSession` 对象。
- 首次请求调用工具时，`ensure_session_initialized()` 会触发鉴权（如有）并调用 `initialize_session()` 构建 `ANPCrawler` 与 `ANPHandler`。
- 之后的请求在同一个 `ServerSession` 上复用既有状态，实现凭证、缓存与上下文隔离。
- 当连接关闭或会话被 FastMCP 回收时，`WeakKeyDictionary` 会自动释放对应资源。

## 请求流程

1. 客户端向 `/mcp` 发送 HTTP 请求（FastMCP 自动处理 `Mcp-Session-Id` 头部）。
2. 服务器进入 `ensure_session_initialized()`：
   - 若已有状态直接返回；
   - 否则调用 `authenticate_and_get_config()` 获取 `SessionConfig`；
   - 根据配置初始化 `ANPCrawler` 与 `ANPHandler` 并写入会话状态。
3. 工具处理函数从状态字典中获取 `anp_handler` 执行业务逻辑。
4. FastMCP 将会话 ID 写入响应头，客户端应在后续请求中透传该值以复用上下文。

## 认证与凭证

- 未注册回调时，`authenticate_and_get_config()` 始终返回默认公共凭证。
- 调用 `set_auth_callback()` 后，可按 Bearer Token、JWT 等策略返回不同的 `SessionConfig`，从而为每个会话指定独立的 DID 文档与私钥。
- 当回调返回 `None` 时，请求会收到 `AUTHENTICATION_FAILED` 错误，工具调用不会执行。

## 调试示例

```bash
# 第一次请求：创建会话并获取返回的 Mcp-Session-Id
curl -i -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'

# 复制响应头中的 Mcp-Session-Id，在后续请求中复用
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -H "Mcp-Session-Id: <响应头中的值>" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"anp_invokeOpenRPC","arguments":{"endpoint":"https://example.com/api","method":"ping"}}}'
```

> FastMCP 客户端（如 Claude Desktop、Claude Code CLI）会自动处理 `Mcp-Session-Id` 的获取与透传，通常无需人工干预。

## 行为特性

- **隔离性**：每个会话拥有独立的 `ANPCrawler` 缓存与鉴权上下文，互不干扰。
- **资源释放**：`WeakKeyDictionary` 与 FastMCP 的会话生命周期绑定，连接关闭后会话对象自动清理。
- **并发支持**：多个会话可并行存在，日志中的 `session_id=id(ctx.session)` 便于区分。
- **调试建议**：将 `--log-level` 设为 `DEBUG` 可观察会话创建、鉴权与释放日志。

## 与旧版实现的区别

- 旧版手工维护 SessionManager 并暴露显式的 `Mcp-Session-Id` 管理接口；新版完全依赖 FastMCP 提供的会话语义，代码量更少、可靠性更高。
- 不再提供会话超时或清理协程；如需自定义生命周期策略，可在 `SESSION_STORE` 外层增加定时任务或持久化存储。

## 常见问题

- **请求提示 `AUTHENTICATION_FAILED`**：确认 `Authorization` 头是否与自定义回调匹配，并检查回调是否返回了 `SessionConfig`。
- **多个客户端共享状态**：确保客户端正确透传 `Mcp-Session-Id`。在自制脚本中需要手动保存并重用响应头。
- **自定义凭证未生效**：确认回调返回的文件路径存在且可读，错误会在日志中显示为 `Failed to initialize session`。
