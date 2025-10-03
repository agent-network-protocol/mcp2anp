# MCP2ANP 远程服务器使用指南

## 概述

MCP2ANP 远程服务器使用官方 MCP SDK 构建，支持 HTTP 传输协议，可通过标准的 MCP 客户端访问。

## 架构设计

### 共享模块

两种模式共享核心的工具处理逻辑：

- `mcp2anp/core/handlers.py`: 共享的 ANP 工具处理类
  - `ANPHandler`: 处理 fetchDoc 和 invokeOpenRPC 工具
  - `initialize_anp_crawler()`: 初始化 ANPCrawler 实例

### 本地服务器

- 文件: `mcp2anp/server.py`
- 协议: MCP stdio
- 用途: Claude Desktop、Cursor 等 MCP 客户端

### 远程服务器

- 文件: `mcp2anp/server_remote.py`
- 协议: MCP over HTTP（官方 MCP SDK）
- 传输: HTTP
- 用途: 远程调用、Web 集成

## 安装

首先安装依赖：

```bash
uv sync
```

## 使用方法

### 1. 本地模式（stdio）

这是原有的运行模式，适用于 Claude Desktop 等应用：

```bash
# 使用统一CLI
uv run mcp2anp local

# 或直接运行
uv run mcp2anp-local

# 或使用模块方式
uv run python -m mcp2anp.server
```

配置示例（Claude Desktop `config.json`）：

```json
{
  "mcpServers": {
    "mcp2anp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp2anp",
        "run",
        "mcp2anp-local"
      ]
    }
  }
}
```

### 2. 远程模式（HTTP）

#### 启动服务器

```bash
# 使用统一CLI（推荐）
uv run mcp2anp remote --host 0.0.0.0 --port 8000

# 或直接运行
uv run mcp2anp-remote

# 或使用模块方式
uv run python -m mcp2anp.server_remote
```

#### 可选参数

```bash
uv run mcp2anp remote \
  --host 0.0.0.0 \          # 绑定地址（默认: 0.0.0.0）
  --port 8000 \              # 端口（默认: 8000）
  --log-level INFO           # 日志级别（默认: INFO）
```

## 在 Claude Desktop 中配置

### 使用 HTTP 传输

```bash
# 添加远程 MCP 服务器
claude mcp add --transport http mcp2anp-remote http://localhost:8000

# 如果服务器需要认证
claude mcp add --transport http secure-mcp2anp https://your-server.com/mcp \
  --header "Authorization: Bearer your-token"

# 或使用 API Key
claude mcp add --transport http secure-mcp2anp https://your-server.com/mcp \
  --header "X-API-Key: your-api-key"
```

### 配置示例

在 Claude Desktop 的 MCP 配置文件中：

```json
{
  "mcpServers": {
    "mcp2anp-remote": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-http", "http://localhost:8000"],
      "env": {}
    },
    "secure-mcp2anp": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-http",
        "https://your-server.com/mcp",
        "--header",
        "Authorization: Bearer your-token"
      ],
      "env": {}
    }
  }
}
```

## 服务器特性

- **标准 MCP 协议**: 使用官方 MCP SDK，兼容所有 MCP 客户端
- **HTTP 传输**: 支持远程访问，无需本地安装
- **工具支持**:
  - `anp.fetchDoc`: 抓取并解析 ANP 文档
  - `anp.invokeOpenRPC`: 调用 OpenRPC 端点
- **DID 认证**: 自动使用默认公共 DID 凭证，支持自定义 DID

## 环境变量

```bash
# 自定义 DID 凭证
ANP_DID_DOCUMENT_PATH=/path/to/did-doc.json
ANP_DID_PRIVATE_KEY_PATH=/path/to/private-key.pem

# 日志级别
LOG_LEVEL=DEBUG
```

## 部署建议

### 开发环境

```bash
# 启动服务器
uv run mcp2anp remote --host 0.0.0.0 --port 8000 --log-level DEBUG
```

### 生产环境

```bash
# 设置环境变量
export ANP_DID_DOCUMENT_PATH="/path/to/did-doc.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/private-key.pem"

# 启动服务器
uv run mcp2anp remote --host 0.0.0.0 --port 8000
```

### Docker 部署

创建 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY . .

# 安装依赖
RUN uv sync

# 暴露端口
EXPOSE 8000

# 启动服务器
CMD ["uv", "run", "mcp2anp", "remote", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：

```bash
docker build -t mcp2anp-remote .
docker run -p 8000:8000 \
  -e ANP_DID_DOCUMENT_PATH=/app/did-doc.json \
  -e ANP_DID_PRIVATE_KEY_PATH=/app/private-key.pem \
  mcp2anp-remote
```

## 安全注意事项

1. **HTTPS**
   - 生产环境建议使用反向代理（如 Nginx）配置 HTTPS
   - 或使用云服务提供商的负载均衡器

2. **DID 凭证**
   - 将 DID 文档和私钥存储在安全位置
   - 通过环境变量传递路径，不要硬编码

3. **访问控制**
   - 使用防火墙限制访问IP
   - 考虑实现速率限制

## 与本地模式对比

| 特性 | 本地模式 (stdio) | 远程模式 (HTTP) |
|-----|----------------|----------------|
| 通信协议 | MCP stdio | MCP over HTTP |
| 鉴权方式 | 无（本地信任） | HTTP 头认证 |
| 适用场景 | Claude Desktop | Web 应用、远程调用 |
| 部署复杂度 | 简单 | 中等 |
| 网络要求 | 无 | 需要网络访问 |
| 并发支持 | 单连接 | 多连接 |

## 故障排查

### 连接问题

```
Failed to connect to MCP server
```

解决：
- 确保服务器正在运行
- 检查端口是否正确
- 验证网络连接

### ANP 未初始化

```json
{
  "ok": false,
  "error": {
    "code": "ANP_NOT_INITIALIZED",
    "message": "ANPCrawler not initialized..."
  }
}
```

解决：检查 DID 凭证路径是否正确，或使用默认的公共凭证。

### 端口被占用

```
ERROR: [Errno 48] Address already in use
```

解决：更换端口或停止占用该端口的进程。

## 下一步

- 查看 [README.md](../README.md) 了解项目整体介绍
- 查看 [spec.md](../spec.md) 了解技术实现细节
- 查看 [examples/](../examples/) 了解测试示例