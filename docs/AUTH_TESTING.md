# 远程服务器鉴权测试指南

本文档说明如何在新版 `mcp2anp.server_remote` 上验证 Bearer Token 鉴权逻辑。当前实现依赖 `set_auth_callback()` 注册自定义回调，无需命令行开关。

## 测试前准备

1. **示例脚本**  
   创建 `scripts/remote_server_with_auth.py`：

   ```python
   from mcp2anp.server_remote import (
       SessionConfig,
       set_auth_callback,
       main as remote_main,
   )

   FIXED_TOKEN = "test-secret-token-12345"

   def auth_callback(token: str) -> SessionConfig | None:
       if token == FIXED_TOKEN:
           return SessionConfig(
               did_document_path="docs/did_public/public-did-doc.json",
               private_key_path="docs/did_public/public-private-key.pem",
           )
       return None

   if __name__ == "__main__":
       set_auth_callback(auth_callback)
       remote_main()
   ```

2. **开启服务器**

   ```bash
   uv run python scripts/remote_server_with_auth.py --host 127.0.0.1 --port 8001
   ```

   服务器启动后记下端口（此处为 8001），以下测试均以此为例。

## 手动测试用例

### 1. 未携带 Token

```bash
curl -X POST http://127.0.0.1:8001/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'
```

**预期**：返回 `AUTHENTICATION_FAILED`。

### 2. 正确的 Bearer Token

```bash
curl -X POST http://127.0.0.1:8001/mcp \
     -H "Authorization: Bearer test-secret-token-12345" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'
```

**预期**：获取正常的工具调用响应。

### 3. 错误的 Bearer Token

```bash
curl -X POST http://127.0.0.1:8001/mcp \
     -H "Authorization: Bearer wrong-token" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'
```

**预期**：返回 `AUTHENTICATION_FAILED`。

### 4. 多租户凭证

将脚本中的 `auth_callback` 改为根据不同 token 返回不同的 `SessionConfig`，验证是否能够为每个会话注入独立凭证。

## 自动化测试建议

- 更新 `examples/test_remote_auth.py` 使用上述脚本方案：  
  - 启动自定义服务器进程；  
  - 通过 HTTP 客户端验证无 Token、正确 Token、错误 Token 等场景；  
  - 结束后停止进程并清理。
- 使用 `pytest` 或 `httpx.AsyncClient` 执行请求可获得更稳定的断言。

## 日志确认要点

- `Initializing session`：会话首次创建。
- `Authentication succeeded` / `AUTHENTICATION_FAILED`：鉴权结果。
- `Session initialized successfully`：`ANPCrawler` 创建成功。

启用 `--log-level DEBUG` 可获得更详细的上下文，用于排查凭证路径或 token 解析问题。
