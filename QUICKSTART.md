# MCP2ANP 快速开始

## 🚀 5 分钟快速开始

### 1. 安装依赖

```bash
cd /Users/cs/work/mcp2anp
uv sync
```

### 2. 配置 DID 认证（可选）

#### 使用默认凭证（开发测试）
无需配置，直接运行即可。

#### 使用自定义凭证（生产环境）
```bash
export ANP_DID_DOCUMENT_PATH="/path/to/your/did-document.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/your/private-key.pem"
```

### 3. 运行演示

```bash
uv run python examples/mcp_client_demo.py
```

## 📋 命令速查

### 启动服务器

```bash
# 基本启动
uv run python -m mcp2anp.server

# 调试模式
uv run python -m mcp2anp.server --log-level DEBUG

# 查看帮助
uv run python -m mcp2anp.server --help
```

### 查看工具列表

服务器提供 2 个工具：
- `anp.fetchDoc` - 获取 ANP 文档
- `anp.invokeOpenRPC` - 调用 OpenRPC 方法

## 🔧 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANP_DID_DOCUMENT_PATH` | DID 文档路径 | `docs/did_public/public-did-doc.json` |
| `ANP_DID_PRIVATE_KEY_PATH` | DID 私钥路径 | `docs/did_public/public-private-key.pem` |

## 📖 示例代码

### Python 客户端

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置服务器
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "mcp2anp.server"],
    env=None
)

# 使用服务器
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # 调用工具
        result = await session.call_tool(
            "anp.fetchDoc",
            arguments={"url": "https://agent-connect.ai/agents/test/ad.json"}
        )
```

### 调用 fetchDoc

```python
result = await session.call_tool(
    "anp.fetchDoc",
    arguments={"url": "https://agent-connect.ai/agents/test/ad.json"}
)
```

### 调用 invokeOpenRPC

```python
result = await session.call_tool(
    "anp.invokeOpenRPC",
    arguments={
        "endpoint": "https://agent-connect.ai/agents/test/jsonrpc",
        "method": "echo",
        "params": {"message": "Hello!"}
    }
)
```

## ⚠️ 重要变更

**v0.2.0 起，`anp.setAuth` 工具已移除。**

请使用环境变量配置认证：
```bash
export ANP_DID_DOCUMENT_PATH="..."
export ANP_DID_PRIVATE_KEY_PATH="..."
```

详见 [CHANGES.md](CHANGES.md)

## 📚 完整文档

- [ENV_CONFIG.md](ENV_CONFIG.md) - 环境变量配置详解
- [CHANGES.md](CHANGES.md) - 变更说明和迁移指南
- [README.md](README.md) - 完整项目文档
- [examples/SDK_MIGRATION.md](examples/SDK_MIGRATION.md) - MCP SDK 迁移指南

## 🐛 故障排查

### ANPCrawler 未初始化

```
ANP_NOT_INITIALIZED: ANPCrawler not initialized...
```

**解决**: 检查 DID 凭证文件是否存在，查看服务器启动日志。

### 工具未找到

```
Unknown tool: anp.setAuth
```

**解决**: `anp.setAuth` 已移除，请使用环境变量配置。

## 💡 提示

1. **开发**: 使用默认凭证快速开始
2. **生产**: 配置自定义 DID 凭证
3. **安全**: 私钥文件权限设为 `600`
4. **调试**: 使用 `--log-level DEBUG` 查看详细日志

