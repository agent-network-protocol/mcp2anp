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
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --log-level INFO
```

`server_remote.py` 基于 FastMCP 的 `streamable_http_app`，默认对所有请求开放，并与本地模式共享相同的 DID 凭证加载逻辑（环境变量 > 默认公共凭证）。

#### 常用参数

| 参数 | 说明 | 默认值 |
| ---- | ---- | ------ |
| `--host` | 绑定地址 | `0.0.0.0` |
| `--port` | 监听端口 | `9880` |
| `--log-level` | 日志级别 (`DEBUG/INFO/WARNING/ERROR`) | `INFO` |

> 需要更严格的访问控制时，可通过 `set_auth_callback` 编程方式扩展，详见下文“鉴权机制”。

## 在 Claude Code 中配置

### 使用 HTTP 传输

```bash
claude mcp add --transport http mcp2anp-remote http://localhost:9880/mcp
```

如对外开放的实例启用了自定义鉴权回调，可按需添加 `--header "Authorization: Bearer <token>"` 等额外参数与之配合。

### 使用 curl 测试

```bash
curl -X POST http://localhost:9880/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'
```

## 服务器特性

- **标准 MCP 协议**: 使用官方 MCP SDK，兼容所有 MCP 客户端
- **HTTP 传输**: 支持远程访问，无需本地安装
- **可扩展鉴权**: 通过 `set_auth_callback` 可自定义 Bearer Token、JWT 等验证策略
- **工具支持**:
  - `anp.fetchDoc`: 抓取并解析 ANP 文档
  - `anp.invokeOpenRPC`: 调用 OpenRPC 端点
- **DID 认证**: 自动使用默认公共 DID 凭证，支持自定义 DID

## 鉴权机制

默认情况下，远程服务器允许所有请求并使用公共 DID 凭证。若需要控制访问，可在启动前调用 `set_auth_callback()` 注册自定义回调，通过 `Authorization: Bearer <token>` 头验证请求并按需返回不同的 `SessionConfig`。

### 固定 Token 示例

```python
# scripts/remote_server_with_auth.py
from mcp2anp.server_remote import (
    SessionConfig,
    set_auth_callback,
    main as remote_main,
)

def fixed_token_auth(token: str) -> SessionConfig | None:
    if token == "my-secret-token":
        return SessionConfig(
            did_document_path="docs/did_public/public-did-doc.json",
            private_key_path="docs/did_public/public-private-key.pem",
        )
    return None

if __name__ == "__main__":
    set_auth_callback(fixed_token_auth)
    remote_main()
```

运行：

```bash
uv run python scripts/remote_server_with_auth.py --host 0.0.0.0 --port 9880
```

请求示例：

```bash
curl -X POST http://localhost:9880/mcp \
     -H "Authorization: Bearer my-secret-token" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'
```

### 多租户示例

```python
from mcp2anp.server_remote import SessionConfig, set_auth_callback

def multi_tenant_auth(token: str) -> SessionConfig | None:
    tenant_credentials = {
        "tenant-a": SessionConfig(
            did_document_path="/secure/tenant-a/did.json",
            private_key_path="/secure/tenant-a/key.pem",
        ),
        "tenant-b": SessionConfig(
            did_document_path="/secure/tenant-b/did.json",
            private_key_path="/secure/tenant-b/key.pem",
        ),
    }
    return tenant_credentials.get(token)

set_auth_callback(multi_tenant_auth)
```

### 工作流程

1. 客户端在请求头中附带 `Authorization: Bearer <token>`
2. 服务器提取 token 并调用已注册的鉴权回调
3. 回调返回 `SessionConfig` 时，会话初始化成功并复用其中的 DID 凭证
4. 回调返回 `None` 时，工具调用会收到 `AUTHENTICATION_FAILED` 错误

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
uv run mcp2anp remote --host 0.0.0.0 --port 9880 --log-level DEBUG
```

### 生产环境

```bash
# 设置环境变量
export ANP_DID_DOCUMENT_PATH="/path/to/did-doc.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/private-key.pem"

# 启动服务器
uv run mcp2anp remote --host 0.0.0.0 --port 9880
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
EXPOSE 9880

# 启动服务器
CMD ["uv", "run", "mcp2anp", "remote", "--host", "0.0.0.0", "--port", "9880"]
```

构建和运行：

```bash
docker build -t mcp2anp-remote .
docker run -p 9880:9880 \
  -e ANP_DID_DOCUMENT_PATH=/app/did-doc.json \
  -e ANP_DID_PRIVATE_KEY_PATH=/app/private-key.pem \
  mcp2anp-remote
```

## 安全注意事项

1. **HTTPS**
   - 生产环境建议使用反向代理（如 Nginx）配置 HTTPS
   - 或使用云服务提供商的负载均衡器

2. **访问鉴权**
   - 生产环境建议通过 `set_auth_callback` 实现 Bearer Token 或 JWT 校验
   - Token 应足够长且随机（推荐至少 32 字符）
   - 定期轮换凭证，并使用环境变量或密钥管理服务分发
   - 在日志中避免记录完整凭证

3. **DID 凭证**
   - 将 DID 文档和私钥存储在安全位置
   - 通过环境变量传递路径，不要硬编码

4. **访问控制**
   - 使用防火墙限制访问IP
   - 考虑实现速率限制
   - 监控异常请求模式

## 与本地模式对比

| 特性 | 本地模式 (stdio) | 远程模式 (HTTP) |
|-----|----------------|----------------|
| 通信协议 | MCP stdio | MCP over HTTP |
| 鉴权方式 | 无（本地信任） | 可通过回调扩展（Bearer/JWT） |
| 适用场景 | Claude Desktop | Web 应用、远程调用 |
| 部署复杂度 | 简单 | 中等 |
| 网络要求 | 无 | 需要网络访问 |
| 并发支持 | 单连接 | 多连接 |
| 安全性 | 依赖本地环境 | 可叠加鉴权与 HTTPS |

## 故障排查

### 连接问题

```
Failed to connect to MCP server
```

解决：
- 确保服务器正在运行
- 检查端口是否正确
- 验证网络连接

### 鉴权失败

```json
{
  "ok": false,
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Authentication failed"
  }
}
```

解决：
- 检查是否提供了 `Authorization` 头
- 验证 Bearer Token 是否正确
- 确认自定义 `set_auth_callback` 是否返回了有效的 `SessionConfig`
- 查看服务器日志了解详细错误信息

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
