# 有状态会话模式 - 快速开始

## 概述

MCP2ANP 远程服务器现在支持基于 `Mcp-Session-Id` 的有状态会话模式，每个会话拥有独立的 ANPCrawler 和 ANPHandler 实例。

## 快速开始

### 1. 启动服务器

```bash
# 无鉴权模式（使用默认公共 DID 凭证）
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 启用鉴权模式
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token my-secret-token
```

### 2. 客户端使用

#### 首次请求（创建会话）

```bash
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}' \
     -i
```

响应头会包含 `Mcp-Session-Id`：

```
Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000
```

#### 后续请求（使用会话 ID）

```bash
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -H "Mcp-Session-Id: 550e8400-e29b-41d4-a716-446655440000" \
     -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"anp_invokeOpenRPC","arguments":{...}}}'
```

### 3. 运行测试

```bash
# 启动服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 在另一个终端运行测试
uv run python examples/test_stateful_session.py
```

## 主要特性

- ✅ **会话隔离**: 每个会话拥有独立的 ANPCrawler 和 ANPHandler
- ✅ **自动管理**: 服务器自动管理会话创建和验证
- ✅ **灵活鉴权**: 支持自定义鉴权回调，根据 token 返回不同的 DID 凭证
- ✅ **CORS 支持**: 响应头显式暴露 `Mcp-Session-Id`
- ✅ **错误处理**: 完善的错误处理和状态码

## 自定义鉴权示例

```python
from mcp2anp.server_remote import set_auth_callback, SessionConfig

def my_auth_callback(token: str) -> SessionConfig | None:
    """根据 token 返回对应用户的 DID 凭证。"""
    if token == "user1-token":
        return SessionConfig(
            did_document_path="/path/to/user1/did-doc.json",
            private_key_path="/path/to/user1/private-key.pem"
        )
    elif token == "user2-token":
        return SessionConfig(
            did_document_path="/path/to/user2/did-doc.json",
            private_key_path="/path/to/user2/private-key.pem"
        )
    return None  # 鉴权失败

set_auth_callback(my_auth_callback)
```

## 文档

- **详细文档**: [docs/STATEFUL_SESSION.md](docs/STATEFUL_SESSION.md)
- **修改总结**: [STATEFUL_SESSION_CHANGES.md](STATEFUL_SESSION_CHANGES.md)
- **测试脚本**: [examples/test_stateful_session.py](examples/test_stateful_session.py)

## 破坏性变更

⚠️ **鉴权回调签名变更**

- **旧**: `Callable[[str], bool]` - 返回是否通过验证
- **新**: `Callable[[str], SessionConfig | None]` - 返回会话配置或 None

如果你有自定义鉴权回调，需要更新：

```python
# 旧的鉴权回调
def old_auth(token: str) -> bool:
    return token == "valid"

# 新的鉴权回调
def new_auth(token: str) -> SessionConfig | None:
    if token == "valid":
        return SessionConfig(
            did_document_path="/path/to/did-doc.json",
            private_key_path="/path/to/private-key.pem"
        )
    return None
```

## Claude Code 集成

Claude Code 会自动管理会话 ID，无需手动处理：

```bash
# 添加远程服务器
claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp

# 有鉴权
claude mcp add --transport http mcp2anp-remote http://YOUR_IP:9880/mcp \
  --header "Authorization: Bearer my-secret-token"
```

## 技术架构

```
请求 → AuthMiddleware → 检查 Mcp-Session-Id
                           ↓
                    存在？验证会话
                           ↓
                    不存在？鉴权 + 创建会话
                           ↓
                    设置 ContextVar
                           ↓
                    工具函数获取会话状态
                           ↓
                    使用会话的 ANPHandler
                           ↓
                    返回响应 + Mcp-Session-Id（新会话）
```

## 未来改进

- [ ] 会话超时和自动清理
- [ ] 会话持久化（Redis）
- [ ] 会话统计和监控
- [ ] 负载均衡支持
