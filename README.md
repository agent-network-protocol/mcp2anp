# MCP2ANP

**MCP to ANP Bridge Server** - 让任何支持 MCP 的应用，像"本地工具"一样访问 ANP 智能体

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 概述

MCP2ANP 是一个 **MCP 桥接服务器**，将 ANP (Agent Network Protocol) 的"爬虫式"交互范式转换为 MCP (Model Control Protocol) 工具，使 Claude Desktop、Cursor、各类 IDE 等 MCP 客户端无需改造即可访问 ANP 智能体。

### 核心特性

- 🔧 **两个核心工具**: `anp.fetchDoc`、`anp.invokeOpenRPC`
- 🔐 **DID 认证支持**: 本地 DID 文档和私钥管理
- 🌐 **协议适配**: ANP 爬虫式交互 ↔ MCP 工具式交互
- 🚀 **双模式支持**: 本地 stdio 模式 + 远程 HTTP API 模式
- 📊 **结构化日志**: 完整的操作追踪和调试信息
- 🧪 **全面测试**: 单元测试和集成测试覆盖

### 运行模式


- **本地模式 (Local stdio)**: 通过标准输入输出与 MCP 客户端通信，适用于 Claude Desktop 等桌面应用。
- **远程模式 (Remote HTTP)**: 通过 FastMCP HTTP 传输提供远程访问，可结合自定义鉴权回调扩展访问控制。

> ⚠️ **重要提示：两种模式的认证方式完全不同！**
>
> -   **本地模式**：认证信息通过**环境变量**或**默认本地 DID 文件**在启动时加载，整个服务进程使用单一的 DID 身份。
> -   **远程模式**：认证通过客户端请求中的 **`X-API-Key`** 请求头进行，每个会话独立认证，支持多用户。

详见 [远程服务器文档](docs/REMOTE_SERVER.md)

## 架构设计

#### 本地模式 (Local Mode)

```mermaid
flowchart LR
    subgraph MCP Client
      U[LLM / 前端] -->|call tool| T[Tools]
    end

    subgraph MCP2ANP Bridge (Local)
      ENV[环境变量/默认凭证] --> AC[ANPCrawler上下文]
      T --> AC
      AC --> DID[DID认证]
      DID --> AGL[agent-connect库]
    end

    subgraph ANP Side
      AGL -->|HTTP+DID| ANP
    end
```

#### 远程模式 (Remote Mode)

```mermaid
flowchart LR
    subgraph MCP Client
      U[LLM / 前端] -->|call tool with API Key| T[Tools]
    end

    subgraph MCP2ANP Bridge (Remote)
      subgraph Session Context
          T --> |extract API Key| Auth[远程认证服务]
          Auth -->|fetches DID| DID_Paths[DID 凭证路径]
          DID_Paths --> AC[ANPCrawler上下文]
      end
      AC --> DID[DID认证]
      DID --> AGL[agent-connect库]
    end

    subgraph ANP Side
      AGL -->|HTTP+DID| ANP
    end
```

## 快速上手

### 1. 安装

```bash
# 克隆项目
git clone git@github.com:agent-network-protocol/mcp2anp.git
cd mcp2anp

# 创建 Python 3.11 虚拟环境
uv venv --python 3.11

# 安装依赖
uv sync
```

### 2. 运行本地模式 (Local Mode)

本地模式通过标准输入/输出 (stdio) 与客户端通信，使用环境变量或默认文件进行认证。

#### A. 启动服务器

```bash
# 使用默认的公共 DID 凭证启动
uv run mcp2anp local --log-level INFO
```

如需使用自定义 DID，请在启动前设置环境变量：
```bash
export ANP_DID_DOCUMENT_PATH="/path/to/your/did-document.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/your/private-key.pem"
uv run python -m mcp2anp.server
```

#### B. 添加到 Claude Code

```bash
# 在 mcp2anp 目录下运行
claude mcp add mcp2anp \
  --env ANP_DID_DOCUMENT_PATH=docs/did_public/public-did-doc.json \
  --env ANP_DID_PRIVATE_KEY_PATH=docs/did_public/public-private-key.pem \
  -- uv run python -m mcp2anp.server
```


### 3. 运行远程模式 (Remote Mode)

远程模式通过 HTTP 提供服务，并强制使用 API Key 进行认证。

> 使用默认远程 mcp 服务器（推荐）

```bash
claude mcp add --transport http mcp2anp-remote https://agent-connect.ai/mcp2anp/mcp --header "X-API-Key: YOUR_API_KEY"
```

#### A. 启动服务器

首先，确保您的 API Key 认证服务正在运行。然后启动远程服务器：
```bash
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880
```

#### B. 添加到 Claude Code

将 `YOUR_API_KEY` 替换为您的有效 API 密钥。
```bash
claude mcp add --transport http mcp2anp-remote https://your-remote-server-url --header "X-API-Key: YOUR_API_KEY"
```

### 4. 运行官方 Demo (验证环境)

项目提供了一个客户端演示脚本，可用于快速验证本地模式是否工作正常。

```bash
uv run python examples/mcp_client_demo.py
```
```json
"mcp2anp": {
    "type": "http",
    "url": "http://your-mcp-server-url/mcp",
    "headers": {
        "X-API-Key": "YOUR_API_KEY"
    },
    "disabled": false
}
```
## 工具说明

本项目提供两个核心工具，关于它们的详细工作流程，请参见紧随其后的 **[核心工具详解](#核心工具详解)** 章节。

-   **`anp.fetchDoc`**: 发现网络资源，如同智能浏览器。
-   **`anp.invokeOpenRPC`**: 执行具体操作，如同提交在线表单。

> **认证注意**: 认证方式取决于服务器的运行模式（本地模式使用环境变量/文件，远程模式使用 API Key）。详情请见上文“快速上手”章节。

## 核心工具详解

MCP2ANP 的核心是两个工具，它们共同实现了在 ANP 网络中的“发现”与“执行”。

### 1. `anp.fetchDoc`：发现网络资源

`anp.fetchDoc` 是您在 ANP 网络中的“眼睛”和“导航器”。它不仅仅是一个简单的内容获取工具，更是探索和理解智能体网络的主要方式。

**工作流类比**:

把它想象成一个智能浏览器。您给它一个 URL，它会：
1.  **访问页面**: 获取该 URL 的内容 (`text` 或 `json`)。
2.  **提取链接**: 智能地解析页面内容，并以结构化的形式返回页面上所有可供下一步操作的“链接” (`links`)。

**典型使用流程**:

1.  **进入网络**: 从一个已知的入口 URL 开始，例如 `https://agent-navigation.com/ad.json`。
    ```json
    // 第一次调用，获取网络入口的描述
    anp.fetchDoc({"url": "https://agent-navigation.com/ad.json"})
    ```
2.  **发现服务**: 在返回结果的 `links` 数组中，寻找您感兴趣的服务或智能体，并获取其 URL。
3.  **深入探索**: 选择一个链接，再次调用 `anp.fetchDoc` 来获取该服务的详细信息或其提供的具体接口。这个过程可以不断重复，就像在网站上点击链接一样，从而在整个 ANP 网络中进行“爬取”。

**关键输出**:

-   `text`/`json`: 资源的内容。
-   `links`: 一个结构化数组，是实现自主导航的关键。每个链接都包含 `url`、`title`（标题）、`description`（描述）和 `rel`（关系，如 `interface` 代表这是一个可调用的接口）等信息。

### 2. `anp.invokeOpenRPC`：执行具体操作

如果说 `anp.fetchDoc` 是“发现”，那么 `anp.invokeOpenRPC` 就是“执行”。当您通过 `fetchDoc` 发现一个可执行的接口（通常是一个 OpenRPC 规范）后，就使用这个工具来调用其中的具体方法。

**工作流类比**:

如果 `fetchDoc` 是导航到一个带有在线表单的网页，那么 `invokeOpenRPC` 就是**填写并提交这个表单**来完成一个实际操作（如预订酒店、查询天气）。

**典型使用流程**:

1.  **发现接口**: 通过 `anp.fetchDoc` 找到一个 `rel` 为 `interface` 的链接，并再次调用 `fetchDoc` 获取其内容。这个内容通常是一个 OpenRPC 规范的 JSON 文件。
2.  **理解接口**: 从 OpenRPC 规范中，您可以了解到：
    -   服务在哪个 `endpoint` URL 上接收请求。
    -   它提供了哪些 `method` (方法)。
    -   每个方法需要什么样的 `params` (参数)。
3.  **调用方法**: 使用从规范中获得的信息，调用 `anp.invokeOpenRPC` 来执行一个具体动作。
    ```json
    // 假设已通过 fetchDoc 了解到有一个 "searchLocations" 方法
    anp.invokeOpenRPC({
      "endpoint": "https://example.com/rpc", // 从规范中获得
      "method": "searchLocations",           // 从规范中获得
      "params": {                            // 根据规范构建
        "query": "北京天安门",
        "city": "北京"
      }
    })
    ```

通过 `fetchDoc` 的不断发现和 `invokeOpenRPC` 的精确执行，您可以驱动一个智能体完成从信息检索到执行复杂任务的完整工作流。

## 项目结构

```
.
├── mcp2anp/                 # 核心服务实现
│   ├── __main__.py          # 统一CLI入口
│   ├── server.py            # 本地stdio模式服务器
│   ├── server_remote.py     # 远程HTTP模式服务器
│   ├── core/                # 共享核心模块
│   │   └── handlers.py      # ANP工具处理逻辑
│   └── utils/               # 公共模型与日志工具
│       ├── logging.py
│       └── models.py
├── examples/                # 官方示例与辅助脚本
│   ├── mcp_client_demo.py   # ⭐ 推荐：使用官方 MCP SDK 的客户端演示
│   ├── test_with_local_server.py
│   ├── README.md
│   └── SDK_MIGRATION.md
├── docs/                    # 文档与示例配置
│   ├── usage.md
│   ├── REMOTE_SERVER.md     # 远程服务器文档
│   ├── did_public/
│   │   ├── public-did-doc.json
│   │   └── public-private-key.pem
│   └── examples/
│       ├── anp-agent-description.example.json
│       ├── did-document.example.json
│       ├── openrpc-interface.example.json
│       └── private-key.example.pem
├── assets/                  # 参考资源（图示、日志等）
├── spec.md                  # 协议说明草案
├── run_tests.sh             # 本地测试脚本
├── pyproject.toml           # 构建与依赖配置
├── uv.toml                  # uv 设置
└── uv.lock                  # 依赖锁定文件
```

## 开发

### 环境准备

```bash
# 安装开发依赖
uv sync --group dev

# 安装 pre-commit hooks
pre-commit install
```


### 代码质量

```bash
# 格式化代码
uv run black mcp2anp/ tests/

# 代码检查
uv run ruff mcp2anp/ tests/
```

## 使用示例

### 官方 MCP 客户端 Demo（`examples/mcp_client_demo.py`）

`examples/mcp_client_demo.py` 通过 MCP 官方 SDK 的 `stdio_client` 启动 `mcp2anp.server` 并串联所有工具，是最快速了解桥接工作方式的脚本：

```bash
uv run python examples/mcp_client_demo.py
```

脚本会自动：

- 列出 `mcp2anp` 暴露的工具
- 使用 `docs/did_public/` 内的公共凭证初始化 ANP 连接
- 访问 `anp.fetchDoc` 并展示返回的链接
- 调用 `anp.invokeOpenRPC` 的 `echo` 和 `getStatus` 方法验证回路

如需与真实环境交互，可将脚本中的测试 URL 替换为目标 ANP 服务地址。

<details>
<summary>点击查看：一个完整的酒店预订工作流示例</summary>

### 完整的酒店预订工作流

```python
import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 可选：在代码中指定自定义 DID 凭证路径
os.environ.setdefault("ANP_DID_DOCUMENT_PATH", "docs/did_public/public-did-doc.json")
os.environ.setdefault("ANP_DID_PRIVATE_KEY_PATH", "docs/did_public/public-private-key.pem")


async def main() -> None:
    """演示从发现到调用接口的完整流程。"""
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.server"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            agent_doc = await session.call_tool(
                "anp.fetchDoc",
                arguments={
                    "url": "https://grand-hotel.com/agents/hotel-assistant/ad.json"
                },
            )

            booking_result = await session.call_tool(
                "anp.invokeOpenRPC",
                arguments={
                    "endpoint": "https://grand-hotel.com/api/booking",
                    "method": "confirmBooking",
                    "params": {
                        "checkIn": "2025-10-01",
                        "checkOut": "2025-10-03",
                        "roomType": "standard",
                        "guestInfo": {
                            "name": "张三",
                            "email": "zhangsan@example.com",
                        },
                    },
                },
            )

            print("Agent doc:", agent_doc)
            print("Booking result:", booking_result)


asyncio.run(main())
```

</details>

## 配置

### 环境变量

- `ANP_LOG_LEVEL`: 日志级别 (DEBUG, INFO, WARNING, ERROR)
- `ANP_TIMEOUT`: HTTP 请求超时时间（秒）
- `ANP_MAX_RETRIES`: 最大重试次数

### 命令行选项

- `--log-level`: 设置日志级别、

## 安全注意事项

- ⚠️ **DID 私钥保护**: 不要将私钥文件提交到版本控制
- 🔒 **本地运行**: 服务器仅在本地运行，不暴露到网络
- 🛡️ **输入验证**: 所有工具输入都经过 Pydantic 验证
- 📝 **审计日志**: 所有操作都有详细的结构化日志

## 贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 相关项目

- [Agent Connect](https://github.com/example/agent-connect) - ANP 协议实现
- [MCP SDK](https://github.com/modelcontextprotocol/python-sdk) - MCP Python SDK

## 支持

- 📖 [详细文档](docs/usage.md)
- 🐛 [问题报告](https://github.com/example/mcp2anp/issues)
- 💬 [讨论区](https://github.com/example/mcp2anp/discussions)
