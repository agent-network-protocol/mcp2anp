# 🚀 远程服务器快速入门指南（FastAPI 版本）

本文档将通过一个完整示例，带你从零开始启动一个基于 **FastAPI + httpx +
uvicorn** 的远程服务器，并实现远程 API Key 认证与 ANP 工具接口。

------------------------------------------------------------------------

## 🧭 核心概念

1.  **HTTP 服务**\
    本项目实现了一个标准的 HTTP 服务（基于 FastAPI）。

2.  **强制认证**\
    所有请求都 **必须** 在请求头中携带有效的 `X-API-Key`。\
    服务器会将此密钥发送至外部认证服务以验证合法性。

3.  **工具接口**\
    服务器暴露两个主要工具：

    -   `/tools/anp.fetchDoc`: 抓取 ANP 文档。
    -   `/tools/anp.invokeOpenRPC`: 调用 OpenRPC 接口。

------------------------------------------------------------------------

## 如何使用



## ⚙️ 一分钟快速上手

以下是完整的启动流程。

### 第 1 步：启动认证服务

在启动主服务前，确保认证服务已运行。\
\> 默认地址为：`http://127.0.0.1:9866/api/v1/mcp-sk-api-keys/verify`

------------------------------------------------------------------------

### 第 2 步：启动远程服务器

运行命令：

``` bash
uv run python -m mcp2anp.server_http --host 0.0.0.0 --port 9880
```

------------------------------------------------------------------------

### 第 3 步：测试 API

``` bash
curl -X POST http://localhost:9880/tools/anp.fetchDoc \
     -H "X-API-Key: YOUR_VALID_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://agent-navigation.com/ad.json"}'
```

返回结果：

-   ✅ **成功**：返回解析后的文档 JSON。\
-   ❌ **失败**：返回 `AUTHENTICATION_FAILED` 或验证错误。

------------------------------------------------------------------------

## 🧩 核心组件说明

### Settings 配置类

用于集中管理配置项（主机、端口、认证路径等）。

``` python
class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 9880
    auth_host: str = "127.0.0.1"
    auth_port: int = 9866
    auth_verify_path: str = "/api/v1/mcp-sk-api-keys/verify"
```

> 可通过环境变量或 `.env` 文件进行覆盖。

------------------------------------------------------------------------

### 认证逻辑

所有请求在进入接口前，都会通过依赖函数 `verify_api_key()` 验证 API Key。

``` python
async def verify_api_key(request: Request, settings: Settings = Depends(get_settings)):
    token = request.headers.get(settings.api_key_header, "").strip()
    if not token:
        raise AuthFailure("Missing X-API-Key")
```

验证逻辑：

1.  从请求头提取 API Key。\
2.  调用外部认证服务进行校验（带重试机制）。\
3.  返回 `SessionConfig`，用于初始化 ANP 工具。

------------------------------------------------------------------------

### 工具接口

#### `/tools/anp.fetchDoc`

``` python
@app.post("/tools/anp.fetchDoc")
async def anp_fetch_doc(payload: FetchDocIn, comps: Components = Depends(get_components)):
    result = await comps.anp_handler.handle_fetch_doc({"url": str(payload.url)})
    return ToolEnvelope(ok=True, data=result)
```

功能： - 拉取指定 URL 的 ANP 文档。\
- 自动提取可跟进链接。

------------------------------------------------------------------------

#### `/tools/anp.invokeOpenRPC`

``` python
@app.post("/tools/anp.invokeOpenRPC")
async def anp_invoke_openrpc(payload: InvokeOpenRPCIn, comps: Components = Depends(get_components)):
    result = await comps.anp_handler.handle_invoke_openrpc(args)
    return ToolEnvelope(ok=True, data=result)
```

功能： - 调用任意符合 JSON-RPC 2.0 协议的 OpenRPC 接口。\
- 支持自定义参数与请求 ID。

------------------------------------------------------------------------

## 🔐 错误与异常处理

  异常类型            状态码   描述
  ------------------- -------- --------------------
  `AuthFailure`       401      API Key 缺失或无效
  `ValidationError`   422      参数验证失败
  `httpx.HTTPError`   502      认证服务异常
  `Exception`         500      内部未知错误

------------------------------------------------------------------------

## 🧠 高级用法：自定义认证逻辑

如果你希望绕过外部认证服务，可自定义验证逻辑：

``` python
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

运行：

``` bash
uv run python my_server.py
```

------------------------------------------------------------------------

## 🤝 贡献与反馈

-   💬 **讨论与建议**：[GitHub
    Discussions](https://github.com/agent-network-protocol/mcp2anp/discussions)\
-   🐛 **报告问题**：[GitHub
    Issues](https://github.com/agent-network-protocol/mcp2anp/issues)\
-   🔧 **提交代码**：请遵循项目主 `README.md` 的贡献规范。
