# ClaudeCode+K2+mcp2anp

## Claude Code+K2的安装方法

https://mp.weixin.qq.com/s/8D-PTx6PBr2cyveEMdMa7g

## mcp2anp的安装方法

下载开源代码：https://github.com/agent-network-protocol/mcp2anp

```bash
git clone git@github.com:agent-network-protocol/mcp2anp.git
cd mcp2anp
```


创建 Python 3.11 虚拟环境(版本大于3.11也可以)
```bash
uv venv --python 3.11
```

安装依赖
```bash
uv sync
```


## Claude code中添加此mcp server

```bash
cd mcp2anp
claude mcp add mcp2anp \
  --env ANP_DID_DOCUMENT_PATH=docs/did_public/public-did-doc.json \
  --env ANP_DID_PRIVATE_KEY_PATH=docs/did_public/public-private-key.pem \
  -- uv run python -m mcp2anp.server
```

查看mcp安装结果：

```bash
claude mcp list
```

## 使用mcp2anp

打开Claude Code，输入以下命令：

帮我看看ANP的URL： https://agent-connect.ai/agents/test/ad.json  中，有那些可用的工具。

