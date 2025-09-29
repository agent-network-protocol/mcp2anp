````markdown
# ANP Bridge for MCP —— 实现文档

> 让任何支持 **MCP** 的应用，像"本地工具"一样访问 **ANP** 智能体
> 基于 **FastMCP** 构建真正的 MCP 服务器，提供三个核心工具：**设置认证**、**爬取文档** + **调用接口**

---

## 0. 一句话
**MCP→ANP 适配层**：使用 **FastMCP** 构建真正的 MCP 服务器，把 ANP "从入口文档出发、逐步跟进并调用结构化接口"的交互范式，封装为一组 MCP Tools，令 Claude Desktop、Cursor、IDE 等 MCP 客户端可以通过标准 MCP 协议连接访问 ANP 智能体。

---

## 1. 面向的用户
- **MCP 客户端用户**：Claude Desktop、Cursor、各类 IDE、Agent IDE
- **ANP Agent 提供方**：希望快速对接 MCP 生态
- **企业/团队**：要把内部服务以 ANP 暴露、并允许 LLM 客户端可控访问

---

## 2. 问题（Problem）
1. **协议范式差异**：  
   - ANP 是“**爬虫式**”交互：从一个 `AgentDescription` JSON 出发，沿着 `informations/interfaces` 递归发现与调用能力  
   - MCP 是“**工具式**”交互：模型通过 **tools/resources/prompts** 与外部世界沟通
2. **生态割裂**：ANP 端已有多种接口协议（OpenRPC、YAML 结构化/NL、MCP、WebRTC），MCP 客户端难以直接消费
3. **安全与授权**：ANP 侧常用 DIDWBA 等机制；MCP 客户端不应显式接触敏感 token/签名

---

## 3. 方案（Solution）
**基于 FastMCP 构建真正的 MCP 服务器**，提供三个核心工具：
- `anp.setAuth`：设置 DID 认证上下文（使用本地 DID 文档和私钥文件）
- `anp.fetchDoc`：**唯一**允许的 URL 访问入口（抓取/解析 ANP 文档，抽取可跟进链接）
- `anp.invokeOpenRPC`：对 **OpenRPC** 端点发起方法调用（统一错误模型与返回结构）

**技术架构**：
- 使用标准 `mcp` 库创建 MCP 服务器
- 通过 `@server.list_tools()` 和 `@server.call_tool()` 装饰器实现工具
- 支持 stdio 传输协议，可以被任何 MCP 客户端连接
- 集成 `agent-connect` 库处理 ANP 协议交互

> 搭配系统提示词：**"任何 fetchDoc返回文档中的URL 必须使用 `anp.fetchDoc` 拉取；如需执行操作，优先选择结构化接口（OpenRPC/YAML）；若接口要求人工授权，先征得用户确认并回填证据。"**

---

## 4. 总体架构

```mermaid
flowchart LR
    subgraph MCP Client Application
      U[Claude Desktop/Cursor/IDE] -->|MCP Protocol| MCPClient[MCP Client]
    end

    subgraph MCP2ANP Server
      MCPClient -->|stdio transport| MCPServer[MCP Server]
      MCPServer -->|@server.call_tool| T0[anp.setAuth]
      MCPServer -->|@server.call_tool| T1[anp.fetchDoc]
      MCPServer -->|@server.call_tool| T2[anp.invokeOpenRPC]

      T0 --> SessionMgr[Session Manager]
      T1 --> ANPClient[ANP Client]
      T2 --> OpenRPCAdapter[OpenRPC Adapter]

      SessionMgr --> DIDAuth[DID Authentication]
      ANPClient --> SessionMgr
      OpenRPCAdapter --> SessionMgr
    end

    subgraph ANP Ecosystem
      ANPClient -->|HTTP GET + Auth| AgentDesc[Agent Description]
      ANPClient -->|HTTP GET + Auth| InfoDocs[Information Documents]
      ANPClient -->|HTTP GET + Auth| InterfaceDocs[Interface Documents]

      OpenRPCAdapter -->|JSON-RPC 2.0 + Auth| OpenRPCEndpoint[OpenRPC Endpoint]
    end
````

---

## 5. 时序（MVP：订房示例）

```mermaid
sequenceDiagram
  participant App as Claude Desktop/Cursor
  participant MCP as MCP Server
  participant Session as Session Manager
  participant ANP as ANP Agent (Hotel)

  App->>MCP: 连接到 MCP 服务器 (stdio)
  MCP-->>App: 返回可用工具列表 (list_tools)

  App->>MCP: anp.setAuth(didDocumentPath, didPrivateKeyPath)
  MCP->>Session: 加载 DID 文档和私钥
  Session->>Session: 验证 DID 身份
  Session-->>MCP: 设置认证上下文
  MCP-->>App: {ok: true}

  App->>MCP: anp.fetchDoc(agent-description-url)
  MCP->>Session: 获取认证头
  MCP->>ANP: HTTP GET + Authorization header
  ANP-->>MCP: AgentDescription JSON
  MCP->>MCP: 解析文档，提取链接
  MCP-->>App: {ok:true, json:{...}, links:[...]}

  App->>MCP: anp.fetchDoc(openrpc-interface-url)
  MCP->>ANP: HTTP GET + Authorization header
  ANP-->>MCP: OpenRPC Schema
  MCP-->>App: {ok:true, json:{...}, links:[...]}

  App->>MCP: anp.invokeOpenRPC(endpoint, confirmBooking, params)
  MCP->>Session: 获取认证头
  MCP->>ANP: JSON-RPC POST + Authorization header
  ANP-->>MCP: JSON-RPC Response
  MCP-->>App: {ok:true, result:{bookingId:...}}
```

---

## 7. MCP Tools 规范（MVP）

### 7.1 `anp.setAuth`（可选，推荐）

**用途**：为某 DID/域名写入授权上下文（如 DIDWBA token），后续调用自动注入

* **输入**

```json
{
  "didDocumentPath":"docs/public-did-doc.json",
  "didPrivateKeyPath":"docs/public-private-key.pem"
}
```

* **输出**

```json
{ "ok": true }
```

---

### 7.2 `anp.fetchDoc`

**用途**：用**唯一入口**抓取并解析 ANP 文档/描述/媒体元数据，并抽取“可继续跟进”的链接

* **输入**

```json
{
  "url": "https://grand-hotel.com/agents/hotel-assistant/ad.json",
}
```

* **输出**

```json
{
  "ok": true,
  "contentType": "application/json",  // 类型包括：application/json, application/yaml, text/plain
  "text": "{...}",               // 文本原文；二进制以 base64 返回并标注
  "json": { "protocolType": "ANP", "...": "..." },
  "links": [
    { "rel": "interface", "protocol": "openrpc", "url": "https://grand-hotel.com/api/services-interface.json" },
    { "rel": "info", "url": "https://grand-hotel.com/info/hotel-basic-info.json" }
  ]
}
```

* **错误**

```json
{ "ok": false, "error": { "code": "ANP_NOT_FOUND", "message": "404 from origin" } }
```

---

### 7.3 `anp.invokeOpenRPC`

**用途**：调用 OpenRPC 端点（JSON-RPC 2.0）

* **输入**

```json
{
  "endpoint": "https://grand-hotel.com/api/services-interface.json",
  "method": "confirmBooking",
  "params": { "checkIn": "2025-09-30", "checkOut": "2025-10-02", "roomType": "standard" },
  "id": "optional-uuid"
}
```

* **输出（成功）**

```json
{
  "ok": true,
  "result": { "bookingId": "GH-12345", "totalPrice": 299.00 },
  "raw": { "jsonrpc": "2.0", "id": "optional-uuid", "result": { "...": "..." } }
}
```

* **输出（失败）**

```json
{
  "ok": false,
  "error": { "code": "ANP_INVOCATION_FAILED", "message": "JSON-RPC error", "raw": { "code": -32602, "message": "Invalid params" } }
}
```


## 9. 提示词建议（系统/开发者提示）

> * 任何需要打开的 URL，都必须通过 `anp.fetchDoc` 获取，禁止直接访问
> * 如需执行操作，优先选择“结构化接口”（OpenRPC > YAML 结构化 > 其他）
> * 当接口声明 `humanAuthorization: true` 时，先征得用户确认，并把回执写入 `humanAuthorizationEvidence`
> * 控制爬取步数，仅跟进与当前意图相关的链接

## 依赖和运行

### 核心依赖
- `mcp>=1.0.0` - 标准 MCP 服务器库
- `agent-connect>=0.3.7` - 处理 ANP 协议交互
- `pydantic>=2.5.0` - 数据验证和序列化
- `httpx>=0.27.0` - HTTP 客户端
- `cryptography>=41.0.0` - 加密和 DID 处理

### 运行方式

```bash
# 安装依赖
uv sync

# 启动 MCP 服务器
uv run python -m mcp2anp.server

# 开发模式（热重载）
uv run python -m mcp2anp.server --reload

# 指定日志级别
uv run python -m mcp2anp.server --log-level DEBUG
```

### MCP 客户端连接

服务器使用 stdio 传输协议，可以被任何 MCP 客户端连接：

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

### 代码参考

- DID 身份鉴权：参考 `examples/did-auth/` 目录
- 数据爬取：参考 `examples/fetch-data/` 目录
- 工具实现：查看 `src/mcp2anp/tools/` 目录


