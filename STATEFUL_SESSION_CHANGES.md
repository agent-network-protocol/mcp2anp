# 有状态会话模式实现总结

## 修改概述

本次修改为 MCP2ANP 远程服务器添加了基于 `Mcp-Session-Id` 的有状态会话支持。

## 主要改动

### 1. 核心架构变更 (`mcp2anp/server_remote.py`)

#### 新增类和数据结构

- **`SessionConfig`**: 会话配置类，存储 DID 凭证路径
  ```python
  class SessionConfig:
      def __init__(self, did_document_path: str, private_key_path: str)
  ```

- **`SessionState`**: 会话状态类，包含独立的 ANPCrawler 和 ANPHandler
  ```python
  class SessionState:
      def __init__(self, session_id: str, config: SessionConfig)
      def initialize(self) -> None
  ```

- **`SessionManager`**: 会话管理器，管理所有活跃会话
  ```python
  class SessionManager:
      def create_session(self, config: SessionConfig) -> str
      def get_session(self, session_id: str) -> SessionState | None
      def remove_session(self, session_id: str) -> None
  ```

#### 鉴权回调变更

- **旧签名**: `Callable[[str], bool]` - 返回是否通过验证
- **新签名**: `Callable[[str], SessionConfig | None]` - 返回会话配置或 None

```python
# 旧的鉴权回调
def auth_callback(token: str) -> bool:
    return token == "valid-token"

# 新的鉴权回调
def auth_callback(token: str) -> SessionConfig | None:
    if token == "valid-token":
        return SessionConfig(
            did_document_path="/path/to/did-doc.json",
            private_key_path="/path/to/private-key.pem"
        )
    return None
```

#### 中间件增强

`AuthMiddleware` 现在处理：

1. **会话检查**: 检查请求头中的 `Mcp-Session-Id`
2. **会话验证**: 验证会话 ID 是否有效
3. **会话创建**: 首次连接时创建新会话
4. **会话 ID 返回**: 在响应头中返回 `Mcp-Session-Id`（仅新会话）
5. **CORS 支持**: 显式暴露 `Mcp-Session-Id` 头

#### ContextVar 集成

使用 `contextvars.ContextVar` 在异步上下文中传递会话状态：

```python
from contextvars import ContextVar

current_session: ContextVar[SessionState] = ContextVar("current_session", default=None)
```

#### 工具函数修改

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

### 2. 新增文档

- **`docs/STATEFUL_SESSION.md`**: 详细的有状态会话使用文档
  - 架构设计说明
  - 鉴权回调使用指南
  - 客户端使用示例
  - 错误处理说明
  - 技术实现细节

### 3. 新增测试脚本

- **`examples/test_stateful_session.py`**: 有状态会话功能测试脚本
  - 测试会话创建
  - 测试会话复用
  - 测试无效会话 ID 处理

## 技术细节

### 会话生命周期

```
客户端首次请求
    ↓
服务器鉴权（调用 auth_callback）
    ↓
创建 SessionState（初始化 ANPCrawler 和 ANPHandler）
    ↓
生成 UUID 作为会话 ID
    ↓
返回响应 + Mcp-Session-Id 头
    ↓
客户端保存会话 ID
    ↓
后续请求携带 Mcp-Session-Id 头
    ↓
服务器查找并复用会话状态
```

### 会话隔离

每个会话拥有：
- 独立的 `ANPCrawler` 实例
- 独立的 `ANPHandler` 实例
- 独立的 DID 凭证配置
- 独立的缓存状态

### 线程安全

- 使用 `ContextVar` 确保异步上下文隔离
- 会话管理器使用字典存储，适合单进程多协程场景
- 未来可扩展为使用 Redis 等外部存储实现多进程/多服务器支持

## 向后兼容性

### 破坏性变更

1. **鉴权回调签名变更**: 从返回 `bool` 改为返回 `SessionConfig | None`
   - 影响：自定义鉴权回调需要更新
   - 迁移：返回 `SessionConfig` 而不是 `True`，返回 `None` 而不是 `False`

2. **全局 `anp_handler` 移除**: 不再使用全局单例
   - 影响：直接访问 `anp_handler` 的代码需要更新
   - 迁移：通过 `current_session.get()` 获取会话状态

### 兼容性保持

- 命令行参数保持不变
- 工具名称和签名保持不变
- 客户端 API 保持不变（自动处理会话 ID）

## 使用示例

### 基本使用（无鉴权）

```bash
# 启动服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 客户端请求（自动创建会话）
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}' \
     -i
```

### 启用鉴权

```bash
# 启动服务器（固定 token）
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --enable-auth --auth-token my-secret-token

# 客户端请求（需要 Authorization 头）
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer my-secret-token" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}' \
     -i
```

### 自定义鉴权

```python
from mcp2anp.server_remote import set_auth_callback, SessionConfig

def my_auth_callback(token: str) -> SessionConfig | None:
    # 验证 token 并返回对应的 DID 凭证
    user = validate_token(token)
    if not user:
        return None
    
    return SessionConfig(
        did_document_path=f"/path/to/{user.id}/did-doc.json",
        private_key_path=f"/path/to/{user.id}/private-key.pem"
    )

set_auth_callback(my_auth_callback)
```

## 测试

```bash
# 启动服务器
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880

# 运行测试
uv run python examples/test_stateful_session.py
```

## 未来改进方向

1. **会话超时**: 自动清理长时间未使用的会话
2. **会话持久化**: 支持 Redis 等外部存储
3. **会话迁移**: 支持多服务器间的会话迁移
4. **会话监控**: 提供会话统计和监控接口
5. **会话限制**: 限制每个用户的最大会话数

## 文件清单

### 修改的文件
- `mcp2anp/server_remote.py` - 核心实现

### 新增的文件
- `docs/STATEFUL_SESSION.md` - 使用文档
- `examples/test_stateful_session.py` - 测试脚本
- `STATEFUL_SESSION_CHANGES.md` - 本文档

## 提交建议

```bash
git add mcp2anp/server_remote.py
git add docs/STATEFUL_SESSION.md
git add examples/test_stateful_session.py
git commit -m "feat: add stateful session support with Mcp-Session-Id

- Add SessionManager, SessionState, and SessionConfig classes
- Update auth callback to return SessionConfig instead of bool
- Add session management middleware with Mcp-Session-Id header
- Use ContextVar to pass session state to tool functions
- Each session has independent ANPCrawler and ANPHandler
- Add comprehensive documentation and test script

BREAKING CHANGE: Auth callback signature changed from
Callable[[str], bool] to Callable[[str], SessionConfig | None]"
```
