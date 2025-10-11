# examples/test_server_http_e2e.py
"""
端到端 (E2E) 测试：直接连接到已运行的 HTTP 服务器 (0.0.0.0:9880)。
不使用环境变量，全部硬编码。

覆盖：
1) 有效密钥 -> /tools/anp.fetchDoc 放行 (HTTP 200)
2) 缺失密钥 -> 401
3) 无效密钥 -> 401
4) 非法请求体验证 -> 422
5) （可选）/tools/anp.invokeOpenRPC 成功路径（默认跳过，依赖外部 OpenRPC 端点）
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

# ---------------------- 硬编码配置 ----------------------
API_KEY_HEADER = "X-API-Key"
BASE_URL = "http://0.0.0.0:9880"  # 已运行的后端地址
VALID_KEY = "sk_mcp_MW4O4-FECAP-WQPHF-DHIPR-HV7CK-KU2ED-OOB3E-6OVQD-ZA"


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session", autouse=True)
def _server_reachable(base_url):
    """
    会话级探活：如果服务器不可达，则跳过整个测试套。
    首选探测 /openapi.json；若不存在则尝试 OPTIONS /tools/anp.fetchDoc。
    """
    try:
        with httpx.Client(base_url=base_url, timeout=2.0, trust_env=False) as c:
            r = c.get("/openapi.json")
            if r.status_code < 500:
                return
            r = c.options("/tools/anp.fetchDoc")
            if r.status_code < 500:
                return
    except Exception as e:
        pytest.skip(f"后端未就绪或不可达：{e!r}")


@pytest.fixture
async def client(base_url):
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0, trust_env=False) as c:
        yield c


# ---------------------- 用例：anp.fetchDoc（参数化鉴权） ----------------------
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,headers,expect_status,expect_ok",
    [
        ("valid", {API_KEY_HEADER: VALID_KEY}, 200, True),
        ("missing", {}, 401, False),
        ("invalid", {API_KEY_HEADER: "invalid-key"}, 401, False),
    ],
)
async def test_fetch_doc_auth_cases(
    client: httpx.AsyncClient, case, headers, expect_status, expect_ok
):
    r = await client.post(
        "/tools/anp.fetchDoc",
        headers=headers,
        json={"url": "https://agent-navigation.com/ad.json"},
    )
    assert r.status_code == expect_status, f"{case} -> {r.text}"
    body = r.json()

    if expect_ok:
        assert isinstance(body, dict)
        assert body.get("ok") is True
        assert "data" in body and isinstance(body["data"], dict)
    else:
        assert "detail" in body
        if case == "missing":
            assert "Missing" in body["detail"] or "X-API-Key" in body["detail"]
        if case == "invalid":
            assert "Invalid" in body["detail"] or "expired" in body["detail"]


# ---------------------- 用例：请求体验证（422） ----------------------
@pytest.mark.asyncio
async def test_fetch_doc_validation_error(client: httpx.AsyncClient):
    r = await client.post(
        "/tools/anp.fetchDoc",
        headers={API_KEY_HEADER: VALID_KEY},
        json={"url": "not-a-url"},
    )
    assert r.status_code == 422, r.text
    data = r.json()
    assert (
        isinstance(data, dict) and "detail" in data and isinstance(data["detail"], list)
    )
    assert any(
        isinstance(it, dict) and str(it.get("type", "")).startswith("url")
        for it in data["detail"]
    )


# ---------------------- 用例：anp.invokeOpenRPC（成功路径，可选） ----------------------
@pytest.mark.asyncio
async def test_invoke_openrpc_success(client: httpx.AsyncClient):
    payload: dict[str, Any] = {
        "endpoint": "https://api.example.com/openrpc.json",
        "method": "demo.echo",
        "params": {"x": 1, "y": 2},
        "id": "req-1",
    }
    r = await client.post(
        "/tools/anp.invokeOpenRPC",
        headers={API_KEY_HEADER: VALID_KEY},
        json=payload,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert "data" in body and isinstance(body["data"], dict)
