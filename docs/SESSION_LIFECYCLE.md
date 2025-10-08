# 会话生命周期管理

MCP2ANP 远程服务器实现了基于超时机制的会话生命周期管理，包括会话创建、使用和自动清理。

## 会话生命周期

```
创建会话
    ↓
使用会话（每次请求更新最后访问时间）
    ↓
会话结束:
    超时自动清理（服务器后台任务）
```

## 会话超时机制

### 配置参数

启动服务器时可以配置超时参数：

```bash
uv run python -m mcp2anp.server_remote \
  --host 0.0.0.0 \
  --port 9880 \
  --session-timeout 1800 \      # 会话超时时间（秒），默认 1800（30分钟）
  --cleanup-interval 300         # 清理任务执行间隔（秒），默认 300（5分钟）
```

### 工作原理

1. **访问时间更新**：每次请求都会更新会话的 `last_accessed` 时间
2. **后台清理任务**：每隔 `cleanup-interval` 秒执行一次清理
3. **过期判断**：如果 `当前时间 - last_accessed > session-timeout`，则会话过期
4. **自动删除**：清理任务会删除所有过期的会话

### 示例

```python
# 会话状态类
class SessionState:
    def __init__(self, session_id: str, config: SessionConfig):
        self.created_at = time.time()
        self.last_accessed = time.time()
    
    def touch(self) -> None:
        """更新最后访问时间"""
        self.last_accessed = time.time()
    
    def is_expired(self, timeout: int) -> bool:
        """检查会话是否已过期"""
        return time.time() - self.last_accessed > timeout
```

## 会话清理

会话通过超时机制自动清理，无需客户端主动关闭。当会话超过配置的超时时间未被访问时，后台清理任务会自动删除该会话。

## 会话状态跟踪

### SessionState 属性

```python
class SessionState:
    session_id: str              # 会话 ID
    config: SessionConfig        # DID 凭证配置
    anp_crawler: ANPCrawler     # ANP 爬虫实例
    anp_handler: ANPHandler     # ANP 处理器实例
    created_at: float           # 创建时间（Unix 时间戳）
    last_accessed: float        # 最后访问时间（Unix 时间戳）
```

### 日志记录

服务器会记录所有会话相关的操作：

```
# 会话创建
Session created session_id=550e8400-... total_sessions=1

# 会话访问
Using existing session session_id=550e8400-...

# 会话清理（超时）
Cleaning up expired sessions count=2 timeout=1800
Session removed session_id=550e8400-... total_sessions=0
```

## 最佳实践

### 1. 客户端实现

```python
class MCPClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
    
    def request(self, method: str, params: dict):
        """发送请求"""
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        
        response = requests.post(
            f"{self.base_url}/mcp",
            json={"method": method, "params": params},
            headers=headers
        )
        
        # 保存会话 ID
        if "Mcp-Session-Id" in response.headers:
            self.session_id = response.headers["Mcp-Session-Id"]
        
        return response.json()

# 使用客户端
client = MCPClient("http://localhost:9880")
result = client.request("anp_fetchDoc", {"url": "..."})
# 会话会在超时后自动清理
```

### 2. 服务器配置

根据使用场景选择合适的超时时间：

```bash
# 开发环境：较短超时，快速释放资源
uv run python -m mcp2anp.server_remote \
  --session-timeout 600 \      # 10 分钟
  --cleanup-interval 60         # 1 分钟清理一次

# 生产环境：较长超时，更好的用户体验
uv run python -m mcp2anp.server_remote \
  --session-timeout 3600 \     # 1 小时
  --cleanup-interval 300        # 5 分钟清理一次

# 高负载环境：更短超时，更频繁清理
uv run python -m mcp2anp.server_remote \
  --session-timeout 300 \      # 5 分钟
  --cleanup-interval 60         # 1 分钟清理一次
```

### 3. 监控和调试

启用 DEBUG 日志级别查看详细的会话管理信息：

```bash
uv run python -m mcp2anp.server_remote \
  --log-level DEBUG \
  --session-timeout 1800 \
  --cleanup-interval 300
```

日志输出示例：
```
Session created session_id=550e8400-... total_sessions=1
Using existing session session_id=550e8400-...
No expired sessions to clean up total_sessions=1
Session closed by client DELETE request session_id=550e8400-... total_sessions=0
```

## 测试

运行测试脚本验证会话生命周期：

```bash
# 启动服务器（设置较短的超时时间用于测试）
uv run python -m mcp2anp.server_remote --host 0.0.0.0 --port 9880 --session-timeout 60 --cleanup-interval 30

# 运行测试
uv run python examples/test_stateful_session.py
```

测试脚本会验证：
1. ✅ 会话创建和 ID 返回
2. ✅ 会话复用
3. ✅ 使用无效的会话 ID 返回错误
4. ℹ️ 会话超时（需要等待配置的超时时间）

## 性能考虑

### 内存使用

每个会话包含：
- `SessionState` 对象（~1KB）
- `ANPCrawler` 实例（~10-100KB，取决于缓存）
- `ANPHandler` 实例（~1KB）

估算：1000 个活跃会话约占用 10-100MB 内存

### 清理任务开销

清理任务的时间复杂度为 O(n)，其中 n 是会话总数。
- 1000 个会话：< 1ms
- 10000 个会话：< 10ms

建议：
- 会话数 < 1000：`cleanup-interval` 可设为 300 秒
- 会话数 > 1000：`cleanup-interval` 可设为 60 秒

## 未来改进

- [ ] 会话持久化（Redis）支持多服务器部署
- [ ] 会话统计和监控接口
- [ ] 按用户限制最大会话数
- [ ] 会话迁移和负载均衡
- [ ] 优雅关闭时保存会话状态
- [ ] 支持客户端主动关闭会话（如果 MCP 协议未来支持）
