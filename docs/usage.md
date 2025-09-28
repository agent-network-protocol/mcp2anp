# MCP2ANP 使用指南

## 概述

MCP2ANP 是一个本地 MCP 服务器，提供三个核心工具来桥接 MCP 和 ANP 协议：

- `anp.setAuth`: 设置 DID 认证上下文
- `anp.fetchDoc`: 获取和解析 ANP 文档
- `anp.invokeOpenRPC`: 调用 OpenRPC 端点

## 快速开始

### 1. 安装和启动

```bash
# 创建虚拟环境
uv venv --python 3.11

# 安装依赖
uv sync

# 启动服务器
uv run mcp2anp --log-level INFO
```

### 2. 配置认证（可选）

首先设置 DID 认证上下文：

```json
{
  "tool": "anp.setAuth",
  "arguments": {
    "didDocumentPath": "/path/to/your/did-document.json",
    "didPrivateKeyPath": "/path/to/your/private-key.pem"
  }
}
```

### 3. 获取 ANP 文档

使用 `fetchDoc` 获取 ANP 智能体描述：

```json
{
  "tool": "anp.fetchDoc",
  "arguments": {
    "url": "https://grand-hotel.com/agents/hotel-assistant/ad.json"
  }
}
```

响应包含：
- 文档内容（文本和解析的 JSON）
- 可跟进的链接列表
- 内容类型信息

### 4. 调用 OpenRPC 方法

使用发现的接口端点调用方法：

```json
{
  "tool": "anp.invokeOpenRPC",
  "arguments": {
    "endpoint": "https://grand-hotel.com/api/booking-interface.json",
    "method": "searchRooms",
    "params": {
      "checkIn": "2025-10-01",
      "checkOut": "2025-10-03",
      "guests": 2
    }
  }
}
```

## 完整工作流示例

### 酒店预订场景

```bash
# 1. 设置认证（可选）
anp.setAuth({
  "didDocumentPath": "docs/examples/did-document.json",
  "didPrivateKeyPath": "docs/examples/private-key.pem"
})

# 2. 获取智能体描述
anp.fetchDoc({
  "url": "https://grand-hotel.com/agents/hotel-assistant/ad.json"
})

# 3. 获取预订接口规范
anp.fetchDoc({
  "url": "https://grand-hotel.com/api/booking-interface.json"
})

# 4. 搜索可用房间
anp.invokeOpenRPC({
  "endpoint": "https://grand-hotel.com/api/booking",
  "method": "searchRooms",
  "params": {
    "checkIn": "2025-10-01",
    "checkOut": "2025-10-03",
    "guests": 2
  }
})

# 5. 确认预订
anp.invokeOpenRPC({
  "endpoint": "https://grand-hotel.com/api/booking",
  "method": "confirmBooking",
  "params": {
    "checkIn": "2025-10-01",
    "checkOut": "2025-10-03",
    "roomType": "standard",
    "guestInfo": {
      "name": "张三",
      "email": "zhangsan@example.com",
      "phone": "+86-138-0000-0000"
    }
  }
})
```

## 错误处理

所有工具返回统一的错误格式：

```json
{
  "ok": false,
  "error": {
    "code": "ANP_HTTP_ERROR",
    "message": "HTTP 404: Not Found",
    "raw": { /* 原始错误数据 */ }
  }
}
```

常见错误代码：
- `ANP_HTTP_ERROR`: HTTP 请求错误
- `ANP_REQUEST_ERROR`: 网络请求错误
- `ANP_INVOCATION_FAILED`: OpenRPC 调用失败
- `ANP_DID_LOAD_ERROR`: DID 文档加载失败
- `ANP_KEY_LOAD_ERROR`: 私钥加载失败

## 最佳实践

1. **URL 访问规范**: 只使用 `anp.fetchDoc` 访问 URL，不要直接访问
2. **优先级选择**: 优先选择结构化接口（OpenRPC > YAML > 其他）
3. **人工授权**: 当接口要求 `humanAuthorization: true` 时，先征得用户确认
4. **步数控制**: 控制爬取步数，仅跟进与当前意图相关的链接
5. **错误处理**: 始终检查 `ok` 字段确认操作成功

## 配置选项

### 环境变量

- `ANP_LOG_LEVEL`: 日志级别 (DEBUG, INFO, WARNING, ERROR)
- `ANP_TIMEOUT`: HTTP 请求超时时间（秒）
- `ANP_MAX_RETRIES`: 最大重试次数

### 命令行选项

```bash
uv run mcp2anp --help
```

选项：
- `--log-level`: 设置日志级别
- `--reload`: 启用热重载（开发模式）