# AP2 支付流程快速启动指南

本指南说明如何运行完整的 AP2 支付流程演示。

## 架构说明

AP2 支付流程包含三个组件：

1. **merchant_server.py** - 商户服务器，提供购物车授权和支付授权处理接口
2. **mcp2anp.ap2_server** - MCP 服务器，将 AP2 支付流程封装为 MCP tools
3. **mcp_ap2_client_demo.py** - MCP 客户端演示，通过 MCP 协议调用 AP2 功能

## 运行步骤

### 1. 启动商户服务器

在第一个终端中运行：

```bash
cd examples
uv run python merchant_server.py
```

服务器会在默认端口 8889 启动，输出类似：
```
============================================================
AP2 Merchant Server
============================================================
Host: 192.168.x.x
Port: 8889
[Server] Merchant server started
[Server]   URL: http://192.168.x.x:8889
[Server]   DID: did:example:merchant
[Server] Server is running. Press Ctrl+C to stop.
```

### 2. 运行 MCP AP2 客户端演示

在第二个终端中运行：

```bash
cd examples
uv run python mcp_ap2_client_demo.py
```

客户端会自动：
1. 连接到 `mcp2anp.ap2_server`（通过 stdio）
2. 调用 `ap2.createCartMandate` 创建购物车授权
3. 调用 `ap2.sendPaymentMandate` 发送支付授权
4. 完成完整的支付流程

## 工作流程

```
┌─────────────────┐
│ merchant_server │  ← HTTP API 服务器
│   (端口 8889)   │
└────────┬────────┘
         │ HTTP POST
         │ /ap2/merchant/create_cart_mandate
         │ /ap2/merchant/send_payment_mandate
         │
┌────────▼──────────────────────────────┐
│      mcp_ap2_client_demo.py          │
│  (MCP 客户端)                         │
│                                       │
│  ┌─────────────────────────────────┐ │
│  │  ap2.createCartMandate          │ │
│  │  ap2.sendPaymentMandate         │ │
│  └────────────┬────────────────────┘ │
└───────────────┼───────────────────────┘
                │ MCP stdio 协议
                │
┌───────────────▼───────────────┐
│   mcp2anp.ap2_server          │
│   (MCP 服务器)                 │
│                               │
│   - AP2Handler                │
│   - 封装 shopper client 功能  │
└───────────────────────────────┘
```

## 可用的 MCP Tools

### `ap2.createCartMandate`

创建购物车授权请求并发送给商户服务器。

**参数：**
- `merchant_url` (string, required): 商户服务器URL
- `merchant_did` (string, required): 商户DID
- `cart_mandate_id` (string, required): 购物车授权ID
- `items` (array, required): 商品列表
- `shipping_address` (object, required): 配送地址
- `remark` (string, optional): 备注

**返回：**
- `ok`: 是否成功
- `cart_mandate_id`: 购物车授权ID
- `cart_mandate`: 购物车授权详情
- `cart_hash`: 购物车哈希值

### `ap2.sendPaymentMandate`

构建并发送支付授权给商户服务器。

**参数：**
- `merchant_url` (string, required): 商户服务器URL
- `merchant_did` (string, required): 商户DID
- `cart_mandate_id` (string, required): 之前创建的购物车授权ID
- `payment_mandate_id` (string, required): 支付授权ID
- `refund_period` (integer, optional): 退款期限（天，默认30）

**返回：**
- `ok`: 是否成功
- `payment_mandate_id`: 支付授权ID
- `status`: 支付状态
- `payment_id`: 支付ID
- `payment_receipt`: 支付收据（如果可用）
- `fulfillment_receipt`: 履约收据（如果可用）

## 环境变量

可以通过环境变量配置 DID 凭证：

```bash
export ANP_DID_DOCUMENT_PATH=/path/to/did-doc.json
export ANP_DID_PRIVATE_KEY_PATH=/path/to/private-key.pem
```

如果未设置，将使用默认的公共 DID 凭证（`docs/did_public/public-did-doc.json`）。

## 故障排查

### 商户服务器无法启动

- 检查端口 8889 是否被占用
- 检查 DID 文档和密钥文件是否存在

### MCP 客户端连接失败

- 确保 `mcp2anp.ap2_server` 可以正常导入
- 检查 Python 环境和依赖是否正确安装

### 支付流程失败

- 确保商户服务器正在运行
- 检查网络连接和防火墙设置
- 查看日志输出获取详细错误信息

## 下一步

- 查看 `examples/README.md` 了解更多 MCP 客户端使用方法
- 查看 `mcp2anp/ap2_server.py` 了解服务器实现细节
- 查看 `examples/merchant_server.py` 了解商户服务器实现

