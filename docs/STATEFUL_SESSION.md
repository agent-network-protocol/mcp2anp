# 有状态会话模式

MCP2ANP 远程服务器支持基于 `Mcp-Session-Id` 的有状态会话模式。

## 概述

在有状态会话模式下：

1. **会话创建**：客户端首次连接时，服务器进行鉴权并创建会话，通过响应头 `Mcp-Session-Id` 返回会话 ID
2. **会话复用**：后续请求携带 `Mcp-Session-Id` 头，服务器将复用该会话的状态（ANPCrawler 和 ANPHandler）
3. **独立状态**：每个会话拥有独立的 DID 凭证和状态，互不干扰

## 架构设计

### 会话管理器

```python
class SessionManager:
    """管理所有会话状态。"""
    
    def create_session(self, config: SessionConfig) -> str:
        """创建新会话并返回会话 ID。"""
    
    def get_session(self, session_id: str) -> SessionState | None:
        """获取会话状态。"""
    
    def remove_session(self, session_id: str) -> None:
        """删除会话。"""
```

### 会话状态

```python
class SessionState:
    """会话状态，包含 ANPCrawler 和 ANPHandler。"""
    
    def __init__(self, session_id: str, config: SessionConfig):
        self.session_id = session_id
        self.config = config
        self.anp_crawler: ANPCrawler | None = None
        self.anp_handler: ANPHandler | None = None
```

### 会话配置

```python
class SessionConfig:
    """会话配置信息。"""
    
    def __init__(self, did_document_path: str, private_key_path: str):
        self.did_document_path = did_document_path
        self.private_key_path = private_key_path
```

## 鉴权回调

鉴权回调函数的签名已更改为返回 `SessionConfig`：

```python
AuthCallback = Callable[[str], SessionConfig | None]
```

### 默认鉴权回调

```python
def default_auth_callback(token: str) -> SessionConfig | None:
    """默认鉴权回调函数，使用默认的公共 DID 凭证。"""
    # 使用默认的公共 DID 凭证
    from pathlib import Path
    project_root = Path(__file__).parent.parent
    did_document_path = str(project_root / "docs" / "did_public" / "public-did-doc.json")
    private_key_path = str(project_root / "docs" / "did_public" / "public-private-key.pem")
    
    return SessionConfig(
        did_document_path=did_document_path,
        private_key_path=private_key_path
    )
```

### 自定义鉴权回调

你可以设置自定义鉴权回调来根据 token 返回不同的 DID 凭证：

```python
from mcp2anp.server_remote import set_auth_callback, SessionConfig

def custom_auth_callback(token: str) -> SessionConfig | None:
    """根据 token 返回对应用户的 DID 凭证。"""
    # 验证 token
    user = validate_token(token)
    if not user:
        return None
    
    # 返回该用户的 DID 凭证配置
    return SessionConfig(
        did_document_path=f"/path/to/{user.id}/did-doc.json",
        private_key_path=f"/path/to/{user.id}/private-key.pem"
    )

set_auth_callback(custom_auth_callback)
```

## 使用示例

### 启动服务器

```bash
# 无鉴权模式（使用默认公共凭证）
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 启用鉴权（使用固定 token）
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token my-secret-token
```

### 客户端使用

#### 1. 首次请求（创建会话）

```bash
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer my-secret-token" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "anp_fetchDoc",
         "arguments": {
           "url": "https://agent-navigation.com/ad.json"
         }
       }
     }' \
     -i
```

响应头中会包含 `Mcp-Session-Id`：

```
HTTP/1.1 200 OK
Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000
Access-Control-Expose-Headers: Mcp-Session-Id
...
```

#### 2. 后续请求（使用会话 ID）

```bash
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -H "Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000" \
     -d '{
       "jsonrpc": "2.0",
       "id": 2,
       "method": "tools/call",
       "params": {
         "name": "anp_invokeOpenRPC",
         "arguments": {
           "endpoint": "https://example.com/api",
           "method": "someMethod",
           "params": {}
         }
       }
     }'
```

### Python 客户端示例

```python
import requests

base_url = "http://localhost:9880/mcp"
session_id = None

# 首次请求
response = requests.post(
    base_url,
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "anp_fetchDoc",
            "arguments": {"url": "https://agent-navigation.com/ad.json"}
        }
    },
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer my-secret-token"
    }
)

# 保存会话 ID
session_id = response.headers.get("Mcp-Session-Id")
print(f"Session ID: {session_id}")

# 后续请求
response2 = requests.post(
    base_url,
    json={
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "anp_invokeOpenRPC",
            "arguments": {
                "endpoint": "https://example.com/api",
                "method": "someMethod"
            }
        }
    },
    headers={
        "Content-Type": "application/json",
        "Mcp-Session-Id": session_id
    }
)
```

## Claude Code 集成

在 Claude Code 中添加远程服务器：

```bash
# 无鉴权
claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp

# 有鉴权
claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp \
  --header "Authorization: Bearer my-secret-token"
```

Claude Code 会自动管理会话 ID，你无需手动处理。

## CORS 支持

服务器会在响应头中显式暴露 `Mcp-Session-Id` 头，以支持浏览器环境：

```
Access-Control-Expose-Headers: Mcp-Session-Id
```

## 错误处理

### 无效会话 ID

如果提供的会话 ID 无效或已过期，服务器返回 401：

```json
{
  "error": {
    "code": "INVALID_SESSION",
    "message": "Session not found or expired"
  }
}
```

### 鉴权失败

如果鉴权失败，服务器返回 401：

```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Authentication failed"
  }
}
```

### 会话创建失败

如果会话创建失败（例如 DID 凭证无效），服务器返回 500：

```json
{
  "error": {
    "code": "SESSION_CREATION_FAILED",
    "message": "Failed to initialize ANPCrawler: ..."
  }
}
```

## 测试

运行测试脚本：

```bash
# 启动服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 在另一个终端运行测试
uv run python examples/test_stateful_session.py
```

## 技术实现细节

### ContextVar

使用 Python 的 `contextvars` 来在异步上下文中传递会话状态：

```python
from contextvars import ContextVar

current_session: ContextVar[SessionState] = ContextVar("current_session", default=None)
```

### 中间件

`AuthMiddleware` 负责：

1. 检查请求头中的 `Mcp-Session-Id`
2. 如果存在，验证会话并设置到 ContextVar
3. 如果不存在，进行鉴权并创建新会话
4. 在响应头中返回会话 ID（仅新会话）

### 工具函数

工具函数从 ContextVar 获取当前会话：

```python
@mcp.tool()
async def anp_fetchDoc(url: str) -> str:
    session_state = current_session.get()
    if session_state is None or session_state.anp_handler is None:
        # 返回错误
        ...
    
    result = await session_state.anp_handler.handle_fetch_doc({"url": url})
    ...
```

## 未来改进

- [ ] 会话超时和自动清理
- [ ] 会话持久化（Redis 等）
- [ ] 会话统计和监控
- [ ] 会话迁移和负载均衡
