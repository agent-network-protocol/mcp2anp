# 远程服务器鉴权测试文档

## 概述

本文档介绍如何测试 `mcp2anp` 远程服务器的鉴权功能。

## 测试脚本

测试脚本位于：`examples/test_remote_auth.py`

## 测试场景

### 1. 无鉴权模式
测试在不启用鉴权的情况下，所有请求都能通过。

```bash
# 服务器启动命令
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880
```

**预期行为**：
- 不带 Authorization 头的请求能够成功

### 2. 固定 Token 模式
测试使用固定 Bearer Token 进行鉴权。

```bash
# 服务器启动命令
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token test-secret-token-12345
```

**预期行为**：
- 使用正确 token 的请求能够通过
- 使用错误 token 的请求被拒绝（返回 401 + AUTHENTICATION_FAILED）
- 不带 token 的请求被拒绝

### 3. 默认回调模式
测试启用鉴权但不设置固定 token，使用默认回调函数。

```bash
# 服务器启动命令
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth
```

**预期行为**：
- 带任意 token 的请求都能通过（默认回调总是返回 True）
- 不带 token 的请求被拒绝
- 服务器日志中会打印接收到的 token

### 4. 鉴权失败场景
测试各种非法请求场景。

**测试用例**：
- 错误的 Authorization 头格式（如 `Basic` 而不是 `Bearer`）
- 空 Bearer Token

**预期行为**：
- 所有非法请求都应该被拒绝（返回 401 + AUTHENTICATION_FAILED）

## 运行测试

```bash
# 运行完整测试套件
uv run python examples/test_remote_auth.py
```

**测试输出示例**：

```
2025-10-07 22:11:41 [info] 开始远程服务器鉴权功能测试
2025-10-07 22:11:41 [info] ============================================================
2025-10-07 22:11:41 [info] 测试场景 1: 无鉴权模式
2025-10-07 22:11:41 [info] ============================================================
...
2025-10-07 22:11:41 [info] 测试结果汇总
2025-10-07 22:11:41 [info] ============================================================
2025-10-07 22:11:41 [info] 无鉴权模式: ✅ 通过
2025-10-07 22:11:41 [info] 固定 Token 模式: ✅ 通过
2025-10-07 22:11:41 [info] 默认回调模式: ✅ 通过
2025-10-07 22:11:41 [info] 鉴权失败场景: ✅ 通过
2025-10-07 22:11:41 [info] ============================================================
2025-10-07 22:11:41 [info] 🎉 所有测试通过！
```

## 手动测试

### 使用 curl 测试无鉴权模式

```bash
# 启动服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 发送请求（不带 Authorization 头）
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### 使用 curl 测试鉴权模式

```bash
# 启动服务器（启用鉴权）
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token my-secret-token

# 发送请求（带正确的 token）
curl -X POST http://localhost:9880/mcp \
     -H "Authorization: Bearer my-secret-token" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 发送请求（带错误的 token）
curl -X POST http://localhost:9880/mcp \
     -H "Authorization: Bearer wrong-token" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 预期返回: {"error":{"code":"AUTHENTICATION_FAILED","message":"Authentication failed"}}
```

### 在 Claude Code 中测试

```bash
# 添加远程服务器（带鉴权）
claude mcp add --transport http mcp2anp-remote-auth \
  http://localhost:9880/mcp \
  --header "Authorization: Bearer my-secret-token"

# 测试工具调用
# 在 Claude Code 中，系统会自动使用配置的 header
```

## 自定义鉴权逻辑

如果需要更复杂的鉴权逻辑（如从数据库验证 token），可以编写自定义脚本：

```python
from mcp2anp.server_remote import set_auth_callback, main
import click

def custom_auth(token: str) -> bool:
    """自定义鉴权函数。

    Args:
        token: Bearer Token

    Returns:
        bool: 是否通过验证
    """
    # 这里实现你的鉴权逻辑
    # 例如：从数据库查询 token
    if token in load_valid_tokens_from_database():
        logger.info("Token valid", token=token[:10] + "...")
        return True
    else:
        logger.warning("Token invalid", token=token[:10] + "...")
        return False

# 设置自定义鉴权回调
set_auth_callback(custom_auth)

# 启动服务器
if __name__ == "__main__":
    main()
```

## 安全最佳实践

1. **生产环境必须启用鉴权**
   ```bash
   uv run python -m mcp2anp.server_remote --enable-auth --auth-token $(openssl rand -base64 32)
   ```

2. **使用强 Token**
   - 推荐至少 32 字符
   - 使用加密安全的随机生成器

3. **定期更换 Token**
   - 建议每 30-90 天更换一次
   - 记录 token 更换历史

4. **配合 HTTPS 使用**
   - 使用反向代理（Nginx/Caddy）配置 HTTPS
   - 不要在不安全的网络上传输 token

5. **监控和审计**
   - 记录所有鉴权失败的尝试
   - 设置告警规则，检测异常访问模式
   - 定期审查访问日志

## 故障排查

### 鉴权失败但 token 正确

**问题**：设置了正确的 token，但请求仍然被拒绝。

**可能原因**：
1. 服务器没有启用鉴权（缺少 `--enable-auth`）
2. Token 格式错误（不是 `Bearer token` 格式）
3. Token 中包含特殊字符，被 URL 编码

**解决方法**：
- 检查服务器启动日志，确认鉴权已启用
- 确认 `Authorization` 头格式为 `Bearer <token>`
- 查看服务器日志中的详细错误信息

### 无鉴权模式下仍然要求 token

**问题**：没有启用鉴权，但请求仍然被拒绝。

**可能原因**：
- 服务器可能有其他中间件要求鉴权
- 端口被其他启用了鉴权的实例占用

**解决方法**：
- 确认没有使用 `--enable-auth` 参数
- 检查端口是否被正确的进程占用：`lsof -i :9880`
- 重启服务器

## 总结

鉴权功能已完全实现并通过全面测试，支持：
- ✅ 无鉴权模式（开发环境）
- ✅ 固定 Token 模式（简单生产环境）
- ✅ 默认回调模式（调试）
- ✅ 自定义回调模式（复杂场景）
- ✅ 完整的错误处理和日志记录
- ✅ 与 FastMCP 和 uvicorn 的集成
