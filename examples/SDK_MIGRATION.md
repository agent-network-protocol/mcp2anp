# MCP SDK 迁移指南

本文档说明了如何从自定义实现迁移到使用官方 MCP Python SDK。

## 迁移前后对比

### 旧实现（自定义 JSON-RPC 客户端）

```python
class MCPClient:
    def __init__(self, server_command: list[str]):
        self.server_command = server_command
        self.process = None
        self.request_id = 0
    
    async def start(self):
        self.process = subprocess.Popen(...)
        await self._send_initialize()
    
    async def _send_request(self, method, params):
        # 手动构建 JSON-RPC 请求
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, ...}
        # 手动发送和接收
        self.process.stdin.write(...)
        response = self.process.stdout.readline()
        ...
```

**问题**：
- 需要手动处理 JSON-RPC 协议细节
- 需要手动管理进程生命周期
- 缺少类型提示和自动补全
- 没有标准化的错误处理
- 需要自己实现资源清理

### 新实现（使用 MCP SDK）

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 配置服务器参数
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "mcp2anp.server"],
    env=None
)

# 使用 SDK 连接
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # 调用工具
        result = await session.call_tool(
            "anp.fetchDoc",
            arguments={"url": "https://example.com"}
        )
```

**优势**：
- ✅ SDK 自动处理 JSON-RPC 协议
- ✅ 使用 `async with` 自动管理资源
- ✅ 完整的类型提示支持
- ✅ 标准化的错误处理
- ✅ 自动清理连接和进程

## 主要 API 变化

### 1. 初始化和连接

**旧方式**：
```python
client = MCPClient(["uv", "run", "python", "-m", "mcp2anp.server"])
await client.start()
try:
    # 使用客户端
    ...
finally:
    await client.stop()
```

**新方式**：
```python
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "mcp2anp.server"]
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # 使用 session
        ...
# 自动清理
```

### 2. 获取工具列表

**旧方式**：
```python
tools = await client.list_tools()
for tool in tools:
    print(f"{tool['name']}: {tool.get('description')}")
```

**新方式**：
```python
tools_result = await session.list_tools()
for tool in tools_result.tools:
    print(f"{tool.name}: {tool.description or '无描述'}")
```

### 3. 调用工具

**旧方式**：
```python
result = await client.call_tool(
    "anp.fetchDoc",
    {"url": "https://example.com"}
)
# result 是 list[dict]
```

**新方式**：
```python
result = await session.call_tool(
    "anp.fetchDoc",
    arguments={"url": "https://example.com"}
)
# result.content 是 list[Content]，需要使用 model_dump() 转换
content_list = [c.model_dump() for c in result.content]
```

### 4. 结果处理

**旧方式**：
```python
# 结果直接是字典列表
for item in result:
    if item.get("type") == "text":
        print(item.get("text"))
```

**新方式**：
```python
# 结果是 Pydantic 模型
for content in result.content:
    if hasattr(content, 'text'):
        print(content.text)
    # 或转换为字典
    print(content.model_dump())
```

## 迁移步骤

1. **安装依赖**：确保 `mcp` 包已在 `pyproject.toml` 中
   ```toml
   dependencies = [
       "mcp>=1.0.0",
       ...
   ]
   ```

2. **更新导入**：
   ```python
   # 删除
   import subprocess
   import json
   
   # 添加
   from mcp import ClientSession, StdioServerParameters
   from mcp.client.stdio import stdio_client
   ```

3. **重构客户端代码**：
   - 移除自定义的 `MCPClient` 类
   - 使用 `stdio_client` 和 `ClientSession`
   - 使用 `async with` 管理资源

4. **更新工具调用**：
   - 使用 `session.call_tool()` 替代 `client.call_tool()`
   - 注意参数需要放在 `arguments` 键中
   - 处理返回的 Pydantic 模型

5. **测试**：
   ```bash
   uv run python examples/mcp_client_demo.py
   ```

## 注意事项

### 参数命名约定

服务器的工具参数使用 snake_case：
- ✅ `did_document_path`
- ✅ `did_private_key_path`
- ❌ `didDocumentPath` (会报错)

### 返回值处理

SDK 返回的是 Pydantic 模型，不是普通字典：
```python
# ✅ 正确
result = await session.call_tool("anp.fetchDoc", arguments={"url": "..."})
for content in result.content:
    if hasattr(content, 'text'):
        print(content.text)

# ✅ 或转换为字典
content_dicts = [c.model_dump() for c in result.content]

# ❌ 错误 - content 不是字典
for item in result.content:
    print(item['text'])  # AttributeError
```

### 资源管理

使用 `async with` 确保资源正确清理：
```python
# ✅ 推荐 - 自动清理
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        ...

# ❌ 不推荐 - 需要手动清理
read, write = await stdio_client(server_params).__aenter__()
session = ClientSession(read, write)
# ... 容易忘记清理
```

## 完整示例

参见 `examples/mcp_client_demo.py` 获取完整的工作示例，包括：
- 基本用法演示
- 带认证的使用
- 错误处理
- 日志配置

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [本项目 README](../README.md)

