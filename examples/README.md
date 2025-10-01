# MCP 客户端演示示例

这个目录包含了演示如何使用 **MCP 官方 SDK** 创建客户端来调用 mcp2anp 服务器的示例代码。

## 文件说明

### `mcp_client_demo.py`
使用 MCP 官方 SDK 的完整客户端演示脚本，包含：
- `demo_basic_usage()`: 基本使用演示（使用 MCP SDK）
- `demo_with_auth()`: 带认证的使用演示（使用 MCP SDK）

### `simple_example.py`
简化的使用示例，展示最基本的客户端用法。

## 运行演示

### 前置条件
确保你已经安装了项目依赖：
```bash
uv sync
```

### 运行完整演示
```bash
cd examples
uv run python mcp_client_demo.py
```

### 运行简单示例
```bash
cd examples
uv run python simple_example.py
```

## 使用方法（基于 MCP 官方 SDK）

### 基本步骤

1. **导入 MCP SDK**：
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
```

2. **配置服务器参数**：
```python
server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "mcp2anp.server"],
    env=None
)
```

3. **创建连接和会话**：
```python
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        # 在这里使用 session
```

4. **获取工具列表**：
```python
tools_result = await session.list_tools()
tools = tools_result.tools
```

5. **调用工具**：
```python
result = await session.call_tool(
    "anp.fetchDoc",
    arguments={"url": "https://example.com"}
)
```

### 完整示例
```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def my_example():
    # 配置服务器参数
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"],
        env=None
    )

    # 使用 MCP SDK 连接服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 获取工具列表
            tools_result = await session.list_tools()
            print(f"可用工具: {[tool.name for tool in tools_result.tools]}")

            # 调用工具
            result = await session.call_tool(
                "anp.fetchDoc",
                arguments={"url": "https://httpbin.org/json"}
            )
            print(f"结果: {[c.model_dump() for c in result.content]}")

# 运行示例
asyncio.run(my_example())
```

## 可用的 MCP 工具

根据服务器实现，以下工具可用：

### `anp.setAuth`
设置 DID 认证上下文
- `did_document_path`: DID 文档文件路径
- `did_private_key_path`: DID 私钥文件路径

### `anp.fetchDoc`
抓取并解析 ANP 文档
- `url`: 要抓取的文档 URL

### `anp.invokeOpenRPC`
调用 OpenRPC 端点
- `endpoint`: OpenRPC 端点 URL
- `method`: RPC 方法名
- `params`: RPC 参数

## 注意事项

1. **认证文件**: 要使用 `anp.setAuth` 工具，你需要有效的 DID 文档和私钥文件
2. **网络访问**: 某些工具需要网络访问权限
3. **错误处理**: 示例代码包含了基本的错误处理，实际使用时可能需要更详细的错误处理
4. **资源清理**: 使用完客户端后，务必调用 `stop()` 方法停止服务器进程

## MCP SDK 的优势

使用官方 MCP SDK 的好处：

1. **标准化**: 遵循官方 MCP 协议规范，兼容性更好
2. **简化开发**: 自动处理连接管理、协议细节和错误处理
3. **类型安全**: 提供完整的类型提示，开发体验更好
4. **异步上下文管理**: 使用 `async with` 自动处理资源清理
5. **社区支持**: 由 MCP 官方维护，有完善的文档和社区支持

## 扩展使用

你可以基于这些示例创建自己的 MCP 客户端应用程序：

1. 使用 MCP SDK 提供的其他功能（如 prompts、resources 等）
2. 添加更复杂的错误处理和重试逻辑
3. 实现工具调用的批处理或并发执行
4. 添加配置文件支持以简化工具参数设置
5. 集成到你的应用程序中，作为 AI Agent 的工具调用层