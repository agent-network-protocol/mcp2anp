# 环境变量配置说明

## DID 认证凭证配置

MCP2ANP 服务器在启动时需要 DID 认证凭证。可以通过以下环境变量配置：

### 环境变量

- `ANP_DID_DOCUMENT_PATH`: DID 文档 JSON 文件的完整路径
- `ANP_DID_PRIVATE_KEY_PATH`: DID 私钥 PEM 文件的完整路径

### 配置方式

#### 方式 1: 使用默认凭证（推荐开发测试）

如果不设置环境变量，服务器将自动使用项目提供的默认公共 DID 凭证：

```bash
# 直接启动，使用默认凭证
uv run python -m mcp2anp.server
```

默认凭证位置：
- DID 文档: `docs/did_public/public-did-doc.json`
- 私钥: `docs/did_public/public-private-key.pem`

#### 方式 2: 通过环境变量配置（推荐生产环境）

**Linux/macOS:**

```bash
# 临时设置（当前会话）
export ANP_DID_DOCUMENT_PATH="/path/to/your/did-document.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/your/private-key.pem"
uv run python -m mcp2anp.server

# 或者一次性设置
ANP_DID_DOCUMENT_PATH="/path/to/your/did-document.json" \
ANP_DID_PRIVATE_KEY_PATH="/path/to/your/private-key.pem" \
uv run python -m mcp2anp.server
```

**Windows (PowerShell):**

```powershell
$env:ANP_DID_DOCUMENT_PATH="C:\path\to\your\did-document.json"
$env:ANP_DID_PRIVATE_KEY_PATH="C:\path\to\your\private-key.pem"
uv run python -m mcp2anp.server
```

**Windows (CMD):**

```cmd
set ANP_DID_DOCUMENT_PATH=C:\path\to\your\did-document.json
set ANP_DID_PRIVATE_KEY_PATH=C:\path\to\your\private-key.pem
uv run python -m mcp2anp.server
```

#### 方式 3: 使用 .env 文件

创建 `.env` 文件（在项目根目录）：

```bash
# .env
ANP_DID_DOCUMENT_PATH=/path/to/your/did-document.json
ANP_DID_PRIVATE_KEY_PATH=/path/to/your/private-key.pem
```

然后使用支持 `.env` 文件的工具启动：

```bash
# 使用 python-dotenv
pip install python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv()" && uv run python -m mcp2anp.server

# 或者使用 direnv (需要先安装 direnv)
direnv allow
uv run python -m mcp2anp.server
```

## 验证配置

启动服务器时，日志会显示使用的凭证来源：

```
# 使用默认凭证
Using default DID credentials did_doc=docs/did_public/public-did-doc.json private_key=docs/did_public/public-private-key.pem

# 使用环境变量凭证
Using DID credentials from environment variables did_doc=/custom/path/did.json private_key=/custom/path/key.pem
```

## 创建自定义 DID 凭证

### 1. 准备 DID 文档

创建符合 W3C DID 规范的 JSON 文档，例如：

```json
{
  "@context": [
    "https://www.w3.org/ns/did/v1",
    "https://w3id.org/security/suites/jws-2020/v1"
  ],
  "id": "did:example:your-did-identifier",
  "verificationMethod": [
    {
      "id": "did:example:your-did-identifier#key-1",
      "type": "EcdsaSecp256k1VerificationKey2019",
      "controller": "did:example:your-did-identifier",
      "publicKeyJwk": {
        "kty": "EC",
        "crv": "secp256k1",
        "x": "...",
        "y": "..."
      }
    }
  ],
  "authentication": [
    "did:example:your-did-identifier#key-1"
  ]
}
```

### 2. 准备私钥文件

私钥应为 PEM 格式：

```
-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
```

### 3. 配置环境变量

将 DID 文档和私钥文件保存到安全位置，然后配置环境变量指向这些文件。

## 安全建议

1. **不要将私钥提交到版本控制**: 将 `*.pem` 添加到 `.gitignore`
2. **生产环境使用专用凭证**: 不要在生产环境使用默认的公共凭证
3. **限制文件权限**: 
   ```bash
   chmod 600 /path/to/private-key.pem  # 仅所有者可读写
   ```
4. **使用环境变量或密钥管理系统**: 避免在代码中硬编码路径

## 故障排查

### 问题: ANPCrawler 初始化失败

```
Failed to initialize ANPCrawler error=...
```

**解决方案:**
1. 检查 DID 文档和私钥文件是否存在
2. 检查文件路径是否正确（使用绝对路径）
3. 检查文件权限（是否可读）
4. 验证 DID 文档 JSON 格式是否正确
5. 验证私钥 PEM 格式是否正确

### 问题: 工具调用返回 ANP_NOT_INITIALIZED

```json
{
  "ok": false,
  "error": {
    "code": "ANP_NOT_INITIALIZED",
    "message": "ANPCrawler not initialized. Please check DID credentials."
  }
}
```

**解决方案:**
1. 检查服务器启动日志，确认 ANPCrawler 是否成功初始化
2. 检查 DID 凭证配置是否正确
3. 重启服务器

## 示例

### 开发环境（使用默认凭证）

```bash
# 直接启动
uv run python -m mcp2anp.server --log-level DEBUG
```

### 生产环境（使用自定义凭证）

```bash
# 设置环境变量
export ANP_DID_DOCUMENT_PATH="/etc/mcp2anp/production-did.json"
export ANP_DID_PRIVATE_KEY_PATH="/etc/mcp2anp/production-key.pem"

# 启动服务器
uv run python -m mcp2anp.server --log-level INFO
```

### 使用客户端（环境变量会传递给服务器）

```bash
# 设置环境变量
export ANP_DID_DOCUMENT_PATH="/path/to/your/did.json"
export ANP_DID_PRIVATE_KEY_PATH="/path/to/your/key.pem"

# 运行客户端（会启动服务器）
uv run python examples/mcp_client_demo.py
```

