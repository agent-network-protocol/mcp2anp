# MCP2ANP：让 AI 智能体走向互联互通

> 一座连接 MCP 生态与 ANP 网络的桥梁

## 为什么需要 MCP2ANP？

在 AI 智能体快速发展的今天，我们面临一个有趣的悖论：一方面，像 Claude、Cursor 这样的 AI 助手越来越强大，它们通过 MCP（Model Context Protocol）获得了调用本地工具的能力；另一方面，分散在互联网各处的 AI 智能体服务却缺乏统一的发现和调用标准。

**ANP（Agent Network Protocol）** 正是为解决这个问题而生的开放协议，它为 AI 智能体提供了一套标准化的发现、描述和交互规范。但问题来了：如何让已经支持 MCP 的客户端（如 Claude Desktop、Cursor IDE）无缝接入 ANP 网络呢？

这就是 **MCP2ANP** 的使命——作为一座桥梁，让支持 MCP 的客户端像调用本地工具一样使用 ANP 智能体。

## 核心设计思路

### 1. 协议转换：从 ANP Interface 到 MCP Tools

MCP2ANP 的核心创新在于将 ANP 的元素优雅地映射到 MCP 的对应功能上。其中最关键的一点是：

**将 ANP 的 Interface（接口）转换成 MCP 的 Tools（工具）**

在 ANP 网络中，智能体通过 OpenRPC 规范暴露其能力接口。这些接口定义了智能体能做什么、需要什么参数、返回什么结果。而在 MCP 体系中，工具（Tools）是 AI 助手调用外部能力的标准方式。

MCP2ANP 只暴露两个核心工具，实现了"少即是多"的设计哲学：

| MCP 工具 | 功能 | 对应的 ANP 操作 |
|---------|------|----------------|
| `anp.fetchDoc` | 资源发现与探索 | 抓取 ANP 文档，解析 Agent Description、Informations、OpenRPC 接口定义 |
| `anp.invokeOpenRPC` | 能力执行 | 通过 JSON-RPC 2.0 协议调用 ANP 智能体暴露的方法 |

这种设计的妙处在于：

- **通用性**：两个工具覆盖了"发现"和"执行"两大核心场景
- **灵活性**：AI 可以像"爬虫"一样自主探索 ANP 网络，发现新的服务和能力
- **简洁性**：客户端无需了解 ANP 协议细节，只需调用标准 MCP 工具

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   MCP 客户端     │     │   MCP2ANP 桥接   │     │   ANP 网络       │
│  (Claude/Cursor) │────▶│                 │────▶│                 │
│                 │     │  anp.fetchDoc   │     │  Agent Desc     │
│  调用 MCP Tools  │     │  anp.invokeRPC  │     │  OpenRPC Specs  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 2. 身份认证：API Key 到 DID 的优雅转换

安全认证是智能体互联的基石。ANP 网络采用 **DID（去中心化身份）** 作为身份认证机制，这提供了强大的安全保障，但也带来了使用门槛——用户需要管理 DID 文档和私钥文件。

MCP2ANP 在云端部署模式下提供了一个优雅的解决方案：

**MCP 端使用 API Key → 云端自动映射为 ANP 的 DID 身份**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  MCP 客户端  │────▶│  MCP2ANP    │────▶│  DID Host   │────▶│  ANP 网络   │
│             │     │  云端服务    │     │  认证服务    │     │             │
│ X-API-Key   │     │  Header提取  │     │  Key→DID    │     │  DID签名请求 │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

认证流程如下：

1. 用户在 [DID Host](https://didhost.cc) 创建 DID Card 并生成 API Key
2. MCP 客户端请求携带 `X-API-Key` 请求头
3. MCP2ANP 云端服务提取 API Key，调用 DID Host 验证服务
4. 验证成功后获取对应的 DID 凭证路径
5. 后续对 ANP 网络的请求使用该 DID 身份进行签名

这种设计实现了：

- **用户友好**：只需管理一个 API Key，无需处理复杂的 DID 文件
- **安全可靠**：底层仍然使用 DID 签名机制，保证通信安全
- **统一管理**：通过 DID Host 平台集中管理身份和密钥

## 快速上手指南

### 方式一：使用官方托管服务（推荐）

这是最简单的方式，无需安装任何依赖，只需一行命令：

```bash
# 在 Claude Code 中添加 MCP2ANP 服务
claude mcp add --transport http mcp2anp-remote https://agent-connect.ai/mcp2anp/mcp \
  --header "X-API-Key: YOUR_API_KEY"
```

**获取 API Key 的步骤：**

1. 访问 [DID Host](https://didhost.cc) 并登录
2. 创建新的 DID Card，勾选"生成 API Key"
3. 保存生成的 API Key（仅显示一次）

**验证 API Key：**

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://didhost.cc/api/v1/mcp-sk-api-keys/verify" | jq .
```

### 方式二：自托管远程 HTTP 服务

适合需要私有部署或多人共享的场景：

```bash
# 克隆项目
git clone git@github.com:agent-network-protocol/mcp2anp.git
cd mcp2anp

# 安装依赖
uv venv --python 3.11
uv sync

# 启动服务
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880
```

然后在客户端注册：

```bash
claude mcp add --transport http mcp2anp-remote http://your-server:9880/mcp \
  --header "X-API-Key: YOUR_API_KEY"
```

### 方式三：本地 stdio 模式

适合桌面端开发调试：

```bash
# 设置 DID 凭证路径
export ANP_DID_DOCUMENT_PATH="path/to/did-doc.json"
export ANP_DID_PRIVATE_KEY_PATH="path/to/private-key.pem"

# 启动本地服务
uv run python -m mcp2anp.server --log-level INFO
```

## 使用示例

添加服务后，你可以让 AI 助手帮你探索 ANP 网络：

```
用户：帮我查询一下杭州明天的天气

AI 助手：好的，让我通过 ANP 网络查询天气信息。
[调用 anp.fetchDoc 探索 ANP 入口]
[发现天气服务接口]
[调用 anp.invokeOpenRPC 执行查询]

杭州明天天气：晴，气温 15-22°C，东北风 2-3 级...
```

ANP 网络当前提供的能力包括：

- 酒店、景点的查询预订
- 路径规划、地图 API
- 天气、快递等信息查询
- 智能搜索服务

入口 URL：`https://agent-navigation.com/ad.json`

## 总结

MCP2ANP 的核心价值在于：

1. **零改造接入**：MCP 客户端无需任何修改即可访问 ANP 网络
2. **简化认证**：API Key 模式大幅降低了 DID 身份的使用门槛
3. **标准化桥接**：两个核心工具实现了协议的优雅转换

我们相信，AI 智能体的未来是互联互通的。MCP2ANP 作为连接两大生态的桥梁，正在让这个愿景一步步成为现实。

---

**项目地址**：[github.com/agent-network-protocol/mcp2anp](https://github.com/agent-network-protocol/mcp2anp)

**官方托管服务**：`https://agent-connect.ai/mcp2anp/mcp`

**DID 管理平台**：[didhost.cc](https://didhost.cc)

欢迎 Star、Fork 和贡献代码！
