# 重要变更说明

## 认证方式变更

### 变更内容

**之前**: 通过 `anp.setAuth` 工具在运行时设置 DID 认证
```python
await session.call_tool(
    "anp.setAuth",
    arguments={
        "did_document_path": "path/to/did.json",
        "did_private_key_path": "path/to/key.pem"
    }
)
```

**现在**: 通过环境变量在启动时配置 DID 认证
```bash
export ANP_DID_DOCUMENT_PATH="/path/to/did.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/key.pem"
uv run python -m mcp2anp.server
```

### 变更原因

1. **安全性**: 凭证在启动时加载，不通过网络传输
2. **简化**: 减少工具数量，简化客户端调用流程
3. **标准化**: 遵循 12-factor app 原则，使用环境变量配置

### 受影响的部分

#### 1. 服务器端

**移除的工具:**
- `anp.setAuth` - 不再作为 MCP 工具提供

**新增的初始化流程:**
- 在 `main()` 函数中调用 `initialize_anp_crawler()`
- 从环境变量读取 `ANP_DID_DOCUMENT_PATH` 和 `ANP_DID_PRIVATE_KEY_PATH`
- 如果未设置，使用默认凭证: `docs/did_public/public-did-doc.json` 和 `docs/did_public/public-private-key.pem`

**工具变化:**
- `anp.fetchDoc` - 正常工作，使用启动时配置的凭证
- `anp.invokeOpenRPC` - 正常工作，使用启动时配置的凭证

#### 2. 客户端示例

**`examples/mcp_client_demo.py`:**
- 移除了 `anp.setAuth` 的调用
- 简化了演示流程
- 工具数量从 3 个减少到 2 个

**`examples/test_with_local_server.py`:**
- 需要更新（移除 `anp.setAuth` 相关代码）

#### 3. 数据模型

**`mcp2anp/utils/models.py`:**
- 保留 `SetAuthRequest` 模型（向后兼容）
- 简化了其他模型定义

### 迁移指南

#### 如果您之前使用 `anp.setAuth`

**旧代码:**
```python
# 1. 启动服务器
await client.start()

# 2. 设置认证
await client.call_tool("anp.setAuth", {
    "did_document_path": "my-did.json",
    "did_private_key_path": "my-key.pem"
})

# 3. 使用其他工具
await client.call_tool("anp.fetchDoc", {"url": "..."})
```

**新代码:**
```bash
# 1. 设置环境变量
export ANP_DID_DOCUMENT_PATH="my-did.json"
export ANP_DID_PRIVATE_KEY_PATH="my-key.pem"

# 2. 启动服务器（自动加载凭证）
uv run python -m mcp2anp.server
```

```python
# 3. 直接使用工具（无需 setAuth）
await client.start()
await client.call_tool("anp.fetchDoc", {"url": "..."})
```

#### 在客户端脚本中传递环境变量

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 方式 1: 传递当前环境变量
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "mcp2anp.server"],
    env=None  # 使用当前环境
)

# 方式 2: 自定义环境变量
import os
custom_env = os.environ.copy()
custom_env["ANP_DID_DOCUMENT_PATH"] = "/path/to/did.json"
custom_env["ANP_DID_PRIVATE_KEY_PATH"] = "/path/to/key.pem"

server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "mcp2anp.server"],
    env=custom_env
)
```

### 配置默认凭证

如果不设置环境变量，服务器将使用默认凭证：

**默认 DID 文档**: `docs/did_public/public-did-doc.json`
```json
{
  "@context": [...],
  "id": "did:wba:didhost.cc:public",
  "verificationMethod": [...],
  "authentication": [...]
}
```

**默认私钥**: `docs/did_public/public-private-key.pem`
（需要创建此文件）

### 故障排查

#### 问题 1: ANPCrawler 初始化失败

**现象:**
```
Failed to initialize ANPCrawler error=...
```

**解决:**
1. 检查环境变量是否设置正确
2. 检查文件路径是否存在
3. 检查文件权限是否可读
4. 验证 DID 文档和私钥格式

#### 问题 2: 工具调用返回 ANP_NOT_INITIALIZED

**现象:**
```json
{
  "ok": false,
  "error": {
    "code": "ANP_NOT_INITIALIZED",
    "message": "ANPCrawler not initialized..."
  }
}
```

**解决:**
1. 查看服务器启动日志
2. 确认 ANPCrawler 是否成功初始化
3. 检查 DID 凭证配置
4. 重启服务器

#### 问题 3: 找不到 anp.setAuth 工具

**现象:**
```
Unknown tool: anp.setAuth
```

**解决:**
这是预期行为。`anp.setAuth` 已被移除，请改用环境变量配置。

### 测试

运行更新后的演示：

```bash
# 使用默认凭证
uv run python examples/mcp_client_demo.py

# 使用自定义凭证
export ANP_DID_DOCUMENT_PATH="/path/to/did.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/key.pem"
uv run python examples/mcp_client_demo.py
```

### 相关文档

- [ENV_CONFIG.md](ENV_CONFIG.md) - 详细的环境变量配置指南
- [README.md](README.md) - 项目主文档
- [examples/README.md](examples/README.md) - 示例代码说明

### 版本信息

- **变更版本**: v0.2.0
- **变更日期**: 2025-10-01
- **向后兼容**: 否（移除了 `anp.setAuth` 工具）

