# 鉴权和会话管理使用示例

本文档说明如何使用 `mcp2anp` 的鉴权和会话管理功能。

## 概述

`mcp2anp` 使用 FastMCP 的内置会话管理机制，结合自定义鉴权回调函数，为每个客户端连接提供独立的会话状态和 DID 凭证。

## 核心功能

### 1. 默认行为（无鉴权）

默认情况下，服务器不进行鉴权验证，所有连接都使用公共 DID 凭证：

```bash
# 启动服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 客户端连接（无需 Authorization 头）
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}},"id":1}'
```

### 2. 自定义鉴权回调

可以通过 `set_auth_callback()` 函数设置自定义鉴权逻辑：

```python
from mcp2anp.server_remote import set_auth_callback, SessionConfig

def my_auth_callback(token: str) -> SessionConfig | None:
    """自定义鉴权回调函数。

    Args:
        token: 从 Authorization: Bearer <token> 头中提取的 token

    Returns:
        SessionConfig: 鉴权成功，返回该用户的 DID 凭证配置
        None: 鉴权失败
    """
    # 示例：简单的 token 验证
    if token == "my-secret-token":
        return SessionConfig(
            did_document_path="/path/to/user1/did.json",
            private_key_path="/path/to/user1/key.pem"
        )
    elif token == "another-token":
        return SessionConfig(
            did_document_path="/path/to/user2/did.json",
            private_key_path="/path/to/user2/key.pem"
        )
    else:
        # 鉴权失败
        return None

# 在启动服务器前设置鉴权回调
set_auth_callback(my_auth_callback)
```

### 3. 数据库鉴权示例

更实际的例子，从数据库验证 token：

```python
from mcp2anp.server_remote import set_auth_callback, SessionConfig
import sqlite3

def database_auth_callback(token: str) -> SessionConfig | None:
    """从数据库验证 token 并返回用户凭证。"""
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        # 查询 token 对应的用户凭证
        cursor.execute("""
            SELECT did_document_path, private_key_path
            FROM user_credentials
            WHERE token = ? AND active = 1
        """, (token,))

        result = cursor.fetchone()
        conn.close()

        if result:
            did_doc_path, key_path = result
            return SessionConfig(
                did_document_path=did_doc_path,
                private_key_path=key_path
            )
        else:
            return None  # 鉴权失败
    except Exception as e:
        print(f"Database auth error: {e}")
        return None

set_auth_callback(database_auth_callback)
```

### 4. JWT Token 鉴权示例

使用 JWT token 进行鉴权：

```python
from mcp2anp.server_remote import set_auth_callback, SessionConfig
import jwt
from datetime import datetime

SECRET_KEY = "your-secret-key"

def jwt_auth_callback(token: str) -> SessionConfig | None:
    """验证 JWT token 并返回用户凭证。"""
    try:
        # 解码 JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

        # 检查过期时间
        if payload.get("exp") and payload["exp"] < datetime.utcnow().timestamp():
            return None  # Token 已过期

        # 从 payload 中获取用户凭证路径
        user_id = payload.get("user_id")
        if not user_id:
            return None

        return SessionConfig(
            did_document_path=f"/credentials/{user_id}/did.json",
            private_key_path=f"/credentials/{user_id}/key.pem"
        )
    except jwt.InvalidTokenError:
        return None  # Token 无效

set_auth_callback(jwt_auth_callback)
```

## 客户端使用

### 使用 Authorization 头

客户端需要在请求中包含 `Authorization: Bearer <token>` 头：

```bash
# 使用 curl
curl -X POST http://localhost:9880/mcp \
     -H "Authorization: Bearer my-secret-token" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}},"id":1}'
```

### 在 Claude Code 中配置

```bash
# 添加带鉴权的远程服务器
claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp \
    --header "Authorization: Bearer my-secret-token"
```

## 会话管理

### 自动会话初始化

- 当工具函数（`anp_fetchDoc`、`anp_invokeOpenRPC`）首次被调用时，会自动：
  1. 从 HTTP 请求头中提取 `Authorization: Bearer <token>`
  2. 调用鉴权回调函数验证 token
  3. 如果鉴权成功，使用返回的 `SessionConfig` 初始化会话
  4. 创建独立的 `ANPCrawler` 和 `ANPHandler` 实例

### 会话隔离

- 每个客户端连接拥有独立的 `ServerSession`
- 每个会话拥有独立的 DID 凭证和状态
- 使用 `WeakKeyDictionary` 自动管理内存，会话结束时自动释放

### 鉴权失败处理

如果鉴权失败，工具函数会返回错误：

```json
{
  "ok": false,
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Authentication failed. Please provide valid credentials."
  }
}
```

## 完整示例

```python
#!/usr/bin/env python3
"""自定义鉴权的 MCP2ANP 服务器示例。"""

from mcp2anp.server_remote import main, set_auth_callback, SessionConfig

# 定义鉴权回调
def my_auth(token: str) -> SessionConfig | None:
    """简单的 token 验证。"""
    valid_tokens = {
        "user1-token": SessionConfig(
            did_document_path="/creds/user1/did.json",
            private_key_path="/creds/user1/key.pem"
        ),
        "user2-token": SessionConfig(
            did_document_path="/creds/user2/did.json",
            private_key_path="/creds/user2/key.pem"
        ),
    }
    return valid_tokens.get(token)

if __name__ == "__main__":
    # 设置鉴权回调
    set_auth_callback(my_auth)

    # 启动服务器
    main()
```

运行：

```bash
uv run python my_server.py --host 0.0.0.0 --port 9880
```

## API 参考

### `set_auth_callback(callback: AuthCallback | None)`

设置自定义鉴权回调函数。

**参数：**
- `callback`: 鉴权回调函数，接收 token 字符串，返回 `SessionConfig` 或 `None`
  - 返回 `SessionConfig`：鉴权成功
  - 返回 `None`：鉴权失败
  - 设置为 `None`：恢复默认鉴权（使用公共凭证）

### `SessionConfig(did_document_path: str, private_key_path: str)`

会话配置类，存储 DID 凭证路径。

**参数：**
- `did_document_path`: DID 文档 JSON 文件的绝对路径
- `private_key_path`: DID 私钥 PEM 文件的绝对路径

### `default_auth_callback(token: str) -> SessionConfig`

默认鉴权回调函数，总是返回公共 DID 凭证配置。

### `ensure_session_initialized(ctx: Context) -> dict | None`

确保会话已初始化的内部函数。如果未初始化，会进行鉴权并初始化。

**返回：**
- `dict`: 会话状态字典（鉴权成功）
- `None`: 鉴权失败

## 安全建议

1. **使用 HTTPS**：在生产环境中，务必使用 HTTPS 传输 Bearer Token
2. **Token 管理**：
   - 使用强随机 token
   - 实现 token 过期机制
   - 支持 token 撤销
3. **凭证保护**：
   - DID 私钥文件应设置严格的文件权限（如 600）
   - 不要在代码中硬编码凭证路径
   - 使用环境变量或配置文件管理凭证路径
4. **日志安全**：
   - 不要在日志中记录完整的 token
   - 注意敏感信息的脱敏处理

## 故障排查

### 问题：鉴权总是失败

**检查：**
1. 确认 `Authorization` 头格式正确：`Bearer <token>`
2. 检查鉴权回调函数是否正确设置
3. 查看服务器日志中的鉴权相关信息

### 问题：会话状态丢失

**原因：**
- FastMCP 的会话管理基于连接，连接断开后会话会被清理

**解决：**
- 客户端应保持连接或实现重连机制
- 重要状态应持久化到外部存储

### 问题：无法读取 DID 凭证文件

**检查：**
1. 文件路径是否正确（使用绝对路径）
2. 文件权限是否正确
3. 文件格式是否符合要求
