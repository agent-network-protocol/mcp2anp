# MCP2ANP 示例和测试

本目录包含 MCP2ANP 服务器的示例和测试脚本，演示如何使用三个核心工具与 ANP 智能体交互。

## 🎯 测试目标

我们使用高德地图 ANP 智能体作为测试目标：
```
https://agent-connect.ai/agents/travel/mcp/agents/amap/ad.json
```

## 📁 文件说明

### 测试脚本
- `test_example.py` - 完整的示例测试，演示完整的工作流程
- `test_individual_tools.py` - 单独测试每个工具，便于调试
- `create_did_example.py` - 创建 DID 示例文件的辅助脚本

### 示例文件
- `did-example.json` - 示例 DID 文档（测试用）
- `did-private-key.pem` - 示例 DID 私钥（测试用）

⚠️ **注意**: 示例 DID 文件仅用于测试，请勿在生产环境中使用！

## 🚀 快速开始

### 1. 运行测试脚本（推荐）
```bash
# 从项目根目录运行
./run_tests.sh
```

测试脚本提供以下选项：
1. 快速测试 - 验证基本功能
2. 完整示例测试 - 演示完整工作流程
3. 单独工具测试 - 详细测试每个工具
4. 启动 MCP 服务器 - 供客户端连接
5. 全部运行 - 执行所有测试

### 2. 手动运行特定测试

```bash
# 完整示例测试
uv run python examples/test_example.py

# 单独工具测试
uv run python examples/test_individual_tools.py

# 创建新的 DID 示例文件
uv run python examples/create_did_example.py
```

## 🔧 测试内容

### 1. anp.setAuth 测试
- 加载本地 DID 文档和私钥
- 验证 DID 身份格式
- 设置会话级认证上下文

### 2. anp.fetchDoc 测试
- 抓取 Agent Description 文档
- 解析 JSON 内容和提取链接
- 抓取 OpenRPC 接口文档
- 分析可用的 RPC 方法

### 3. anp.invokeOpenRPC 测试
- 识别简单的查询方法
- 构造测试参数
- 执行 JSON-RPC 2.0 调用
- 处理成功和错误响应

## 📊 预期结果

### 成功情况
- ✅ **工具列表**: 应该显示 3 个工具 (setAuth, fetchDoc, invokeOpenRPC)
- ✅ **文档抓取**: 能够获取 Agent Description 和接口文档
- ⚠️ **RPC 调用**: 可能失败（需要有效认证或正确参数）
- ⚠️ **DID 认证**: 可能失败（需要真实的 DID 凭证）

### 常见问题

1. **DID 认证失败**
   ```
   💡 解决方案:
   - 确保 DID 文件格式正确
   - 检查私钥与 DID 文档匹配
   - 对于生产使用，需要真实的 DID 凭证
   ```

2. **OpenRPC 调用失败**
   ```
   💡 这是正常的，可能原因:
   - 需要有效的认证令牌
   - 参数格式不匹配
   - 服务端点暂时不可用
   ```

3. **网络连接问题**
   ```
   💡 解决方案:
   - 检查网络连接
   - 确认目标 URL 可访问
   - 检查防火墙设置
   ```

## 🔍 调试技巧

### 查看详细日志
```bash
# 启用调试日志
uv run python -m mcp2anp.server --log-level DEBUG
```

### 测试特定工具
```python
# 在 Python 中直接测试
import asyncio
import sys
sys.path.insert(0, 'src')

from mcp2anp.server import call_tool

async def test_fetch():
    result = await call_tool("anp.fetchDoc", {
        "url": "https://agent-connect.ai/agents/travel/mcp/agents/amap/ad.json"
    })
    print(result[0].text)

asyncio.run(test_fetch())
```

### 验证 MCP 服务器
```bash
# 检查服务器是否能正常启动
uv run python -m mcp2anp.server --help
```

## 🌐 与 MCP 客户端集成

要将 MCP2ANP 服务器与 MCP 客户端（如 Claude Desktop）集成：

```json
{
  "mcpServers": {
    "mcp2anp": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp2anp.server"],
      "cwd": "/path/to/mcp2anp"
    }
  }
}
```

## 📚 进一步学习

- 查看 `../spec.md` 了解完整的技术规范
- 查看 `../src/mcp2anp/` 了解实现细节
- 参考 ANP 协议文档了解 Agent 交互模式