````markdown
# ANP Bridge for MCP —— 网站方案（提案版）

> 让任何支持 **MCP** 的应用，像“本地工具”一样访问 **ANP** 智能体  
> （MVP：仅用两个工具——**爬取文档** + **调用接口**，先支持 **OpenRPC**，后续扩展 YAML/MCP/WebRTC）

---

## 0. 一句话
**MCP→ANP 适配层**：把 ANP “从入口文档出发、逐步跟进并调用结构化接口”的交互范式，封装为一组 MCP Tools，令 Claude/Cursor/IDE 等 MCP 客户端无需改造即可访问 ANP 智能体。

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
**只用 MCP tools** 实现 MVP：  
- `anp.fetchDoc`：**唯一**允许的 URL 访问入口（抓取/解析 ANP 文档，抽取可跟进链接）  
- `anp.invokeOpenRPC`：对 **OpenRPC** 端点发起方法调用（统一错误模型与返回结构）  
- （可选）`anp.setAuth`：把 DIDWBA 等授权上下文写入服务端会话，`fetchDoc/invoke` 自动注入头。 因为我们的mcp server是本地的server，所以，setAuth传入的是did文档以及对应的did私钥文件。

> 搭配系统提示词：**“任何 fetchDoc返回文档中的URL 必须使用 `anp.fetchDoc` 拉取；如需执行操作，优先选择结构化接口（OpenRPC/YAML）；若接口要求人工授权，先征得用户确认并回填证据。”**

---

## 4. 总体架构

```mermaid
flowchart LR
    subgraph MCP Client
      U[LLM / 前端] -->|call tool| T1[anp.fetchDoc]
      U -->|call tool| T2[anp.invokeOpenRPC]
      U -->|optional| T0[anp.setAuth]
    end

    subgraph ANP Bridge (MCP Server)
      T1 --> P1[解析/抽链/缓存]
      T2 --> A1[OpenRPC 适配器]
      T0 --> S1[会话级授权上下文]
      P1 --> S1
      A1 --> S1
    end

    subgraph ANP Side
      D1[AgentDescription] -.-> D2[Informations]
      D1 -.-> D3[Interfaces(OpenRPC/YAML/...)]
      A1 -->|JSON-RPC| E1[OpenRPC Endpoint]
      P1 -->|HTTP GET| D1
      P1 -->|HTTP GET| D2
      P1 -->|HTTP GET| D3
    end
````

---

## 5. 时序（MVP：订房示例）

```mermaid
sequenceDiagram
  participant Client as MCP Client (Claude/Cursor)
  participant Bridge as ANP Bridge (MCP Server)
  participant Agent as ANP Agent (Hotel)

  Client->>Bridge: anp.setAuth(did, token)  (可选)
  Client->>Bridge: anp.fetchDoc(ad.json)
  Bridge->>Agent: GET ad.json (+Authorization)
  Agent-->>Bridge: AgentDescription
  Bridge-->>Client: 文档+可跟进链接(interfaces, informations)

  Client->>Bridge: anp.fetchDoc(booking-interface.json)
  Bridge->>Agent: GET booking-interface.json
  Agent-->>Bridge: OpenRPC schema
  Bridge-->>Client: 解析后的接口描述(方法列表)


  Client->>Bridge: anp.invokeOpenRPC(endpoint, method, params, evidence)
  Bridge->>Agent: POST JSON-RPC {method, params}
  Agent-->>Bridge: {result}
  Bridge-->>Client: {ok:true, result}
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

## 依赖

依赖agent-connect 3.7版本。

代码参考 examples下面的两个文件夹，一个用于处理did身份鉴权，一个爬取数据。

上面的fetchDoc和invokeOpenRPC 参考examples中的代码实现。


