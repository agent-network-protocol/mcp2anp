# 远程服务器快速入门指南

本文档将通过一个核心示例，指导您如何快速启动并使用远程服务器。

## 核心概念

1.  **HTTP 服务**: 远程服务器是一个 HTTP 服务。
2.  **强制认证**: 所有请求都**必须**在请求头中提供一个有效的 `X-API-Key`。
3.  **外部验证**: 服务器会使用您提供的 API Key，连接一个外部服务来完成认证。

---

## 一分钟快速上手

下面是一个完整的操作流程，只需按顺序执行即可。

### 第 1 步: 启动依赖的认证服务

在启动主服务器前，请确保用于验证 API Key 的外部认证服务正在运行。

*(对于开发环境，该服务通常在 `http://127.0.0.1:9866` 上)*

### 第 2 步: 启动远程服务器

打开一个新终端，运行以下命令：

```bash
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880
```

### 第 3 步: 测试服务器

再打开一个终端，使用 `curl` 命令测试服务器。请将 `YOUR_VALID_API_KEY` 替换为您的有效 API 密钥。

```bash
curl -X POST http://localhost:9880/mcp \
     -H "X-API-Key: YOUR_VALID_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"anp_fetchDoc","arguments":{"url":"https://agent-navigation.com/ad.json"}}}'
```

- **如果成功**，您会看到返回的 JSON 结果。
- **如果失败**，您会看到 `AUTHENTICATION_FAILED` 错误，这通常意味着您的 API Key 不正确或未提供。

### 第 4 步: 在 Claude Code 中使用

```bash
claude mcp add --transport http mcp2anp-remote http://localhost:9880/mcp --header "X-API-Key: YOUR_VALID_API_KEY"
```

---

## 部署到您的服务器

在生产环境中部署远程服务器时，建议使用 Docker。

#### 1. 创建 `Dockerfile`

在项目根目录下创建 `Dockerfile`：

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

# 启动远程服务器
# 注意：我们运行 server_remote, 它不使用环境变量进行认证
CMD ["uv", "run", "python", "-m", "mcp2anp.server_remote", "--host", "0.0.0.0", "--port", "9880"]
```

#### 2. 构建和运行 Docker 容器

```bash
# 构建镜像
docker build -t mcp2anp-remote .

# 运行容器
docker run -p 9880:9880 --name my-mcp-server -d mcp2anp-remote
```

#### 3. 安全建议
- **HTTPS**: 在生产环境，请务必使用反向代理 (如 Nginx) 为您的服务添加 HTTPS 支持。
- **认证服务**: 确保您的 API Key 认证服务是稳定且安全的。

---

## 贡献

我们欢迎任何形式的贡献！如果您发现问题或有改进建议，请通过以下方式参与：

-   **报告问题**: 在项目的 [GitHub Issues](https://github.com/agent-network-protocol/mcp2anp/issues) 页面提交您发现的 Bug 或问题。
-   **提出建议**: 通过 [GitHub Discussions](https://github.com/agent-network-protocol/mcp2anp/discussions) 分享您的想法和建议。
-   **提交代码**: 请遵循项目主 `README.md` 文件中的贡献指南来提交您的代码合并请求 (Pull Request)。

---

<details>
<summary>高级用法：自定义认证逻辑</summary>

如果您不想依赖外部认证服务，可以通过编程方式提供自己的验证逻辑。

**示例**:
```python
# my_server.py
from mcp2anp.server_remote import SessionConfig, set_auth_callback, main

def my_auth_logic(api_key: str) -> SessionConfig | None:
    if api_key == "my-secret-key":
        return SessionConfig(
            did_document_path="docs/did_public/public-did-doc.json",
            private_key_path="docs/did_public/public-private-key.pem",
        )
    return None

if __name__ == "__main__":
    set_auth_callback(my_auth_logic)
    main()
```
然后运行 `uv run python my_server.py` 即可。
</details>
