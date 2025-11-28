# MCP2ANP

> MCP ↔ ANP 桥接服务，让支持 MCP 的客户端像调用本地工具一样使用 ANP 智能体。

## 快速开始

### 第一步：获取 API Key

在使用 MCP2ANP 之前，你需要先获取一个 API Key：

1. 访问 [DID-HOST](https://didhost.cc) 并登录账户
2. 新建 DID Card，在创建流程中勾选"生成 API Key"
3. 将生成的私钥与 API Key 安全保存（它们仅显示一次，丢失后无法恢复）

**验证 API Key（可选）**：

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://didhost.cc/api/v1/mcp-sk-api-keys/verify" | jq .
```

### 第二步：使用官方托管（推荐）

在 Claude 中直接使用官方托管端点，无需安装和配置：

```bash
claude mcp add --transport http mcp2anp-remote https://agent-connect.ai/mcp2anp/mcp \
  --header "X-API-Key: YOUR_API_KEY"
```

将 `YOUR_API_KEY` 替换为你在第一步中获取的 API Key。

### 第三步：本地启动服务器（可选）

如果你需要自托管服务器，可以按照以下步骤操作：

#### 3.1 安装依赖

```bash
git clone git@github.com:agent-network-protocol/mcp2anp.git
cd mcp2anp
uv venv --python 3.11
uv sync
```

#### 3.2 配置 DID 凭证

**方式 1: 使用默认凭证（开发测试）**

直接启动，使用项目提供的默认公共 DID 凭证：

```bash
uv run python -m mcp2anp.server
```

**方式 2: 通过环境变量配置（推荐生产环境）**

```bash
# 设置 DID 文件路径
export ANP_DID_DOCUMENT_PATH="docs/did_public/public-did-doc.json"
export ANP_DID_PRIVATE_KEY_PATH="docs/did_public/public-private-key.pem"

# 启动服务
uv run python -m mcp2anp.server --log-level INFO
```

**方式 3: 在 Claude 中添加本地服务器**

```bash
# 将仓库根目录赋值给变量（替换为你的实际路径）
MCP2ANP_DIR=/Users/yourname/mcp2anp

claude mcp add mcp2anp \
  --env ANP_DID_DOCUMENT_PATH=$MCP2ANP_DIR/docs/did_public/public-did-doc.json \
  --env ANP_DID_PRIVATE_KEY_PATH=$MCP2ANP_DIR/docs/did_public/public-private-key.pem \
  -- uv run --directory $MCP2ANP_DIR python -m mcp2anp.server
```

### 第四步：运行官方 Demo

运行官方演示脚本，查看完整的使用示例：

```bash
uv run python examples/mcp_client_demo.py
```

Demo 会演示：
- 列出可用工具
- 调用 `anp.fetchDoc` 获取智能体描述文档
- 调用 `anp.invokeOpenRPC` 执行 OpenRPC 方法
