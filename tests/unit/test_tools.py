"""Unit tests for MCP tools."""

import pytest
import respx
import httpx

from mcp2anp.tools import SetAuthTool, FetchDocTool, InvokeOpenRPCTool


class TestSetAuthTool:
    """Test cases for SetAuthTool."""

    def test_get_tool_definition(self, set_auth_tool):
        """Test tool definition generation."""
        tool_def = set_auth_tool.get_tool_definition()

        assert tool_def.name == "anp.setAuth"
        assert "DID-based authentication" in tool_def.description
        assert "didDocumentPath" in tool_def.inputSchema["properties"]
        assert "didPrivateKeyPath" in tool_def.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_execute_success(self, set_auth_tool, temp_did_files):
        """Test successful setAuth execution."""
        result = await set_auth_tool.execute({
            "didDocumentPath": temp_did_files["did_document_path"],
            "didPrivateKeyPath": temp_did_files["private_key_path"],
        })

        assert result["ok"] is True
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_execute_invalid_did_document(self, set_auth_tool):
        """Test setAuth with invalid DID document."""
        result = await set_auth_tool.execute({
            "didDocumentPath": "/nonexistent/did-doc.json",
            "didPrivateKeyPath": "/nonexistent/private-key.pem",
        })

        assert result["ok"] is False
        assert result["error"]["code"] == "ANP_DID_LOAD_ERROR"

    @pytest.mark.asyncio
    async def test_execute_missing_arguments(self, set_auth_tool):
        """Test setAuth with missing arguments."""
        with pytest.raises(Exception):  # ValidationError from pydantic
            await set_auth_tool.execute({
                "didDocumentPath": "test.json",
                # missing didPrivateKeyPath
            })


class TestFetchDocTool:
    """Test cases for FetchDocTool."""

    def test_get_tool_definition(self, fetch_doc_tool):
        """Test tool definition generation."""
        tool_def = fetch_doc_tool.get_tool_definition()

        assert tool_def.name == "anp.fetchDoc"
        assert "fetch and parse ANP documents" in tool_def.description
        assert "url" in tool_def.inputSchema["properties"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_success(self, fetch_doc_tool, sample_anp_document):
        """Test successful fetchDoc execution."""
        test_url = "https://test-agent.com/ad.json"

        respx.get(test_url).mock(
            return_value=httpx.Response(
                200,
                json=sample_anp_document,
                headers={"content-type": "application/json"}
            )
        )

        result = await fetch_doc_tool.execute({"url": test_url})

        assert result["ok"] is True
        assert result["contentType"] == "application/json"
        assert result["json"]["protocolType"] == "ANP"
        assert len(result["links"]) > 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_http_error(self, fetch_doc_tool):
        """Test fetchDoc with HTTP error."""
        test_url = "https://test-agent.com/not-found.json"

        respx.get(test_url).mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await fetch_doc_tool.execute({"url": test_url})

        assert result["ok"] is False
        assert "ANP_HTTP_ERROR" in result["error"]["code"]


class TestInvokeOpenRPCTool:
    """Test cases for InvokeOpenRPCTool."""

    def test_get_tool_definition(self, invoke_openrpc_tool):
        """Test tool definition generation."""
        tool_def = invoke_openrpc_tool.get_tool_definition()

        assert tool_def.name == "anp.invokeOpenRPC"
        assert "OpenRPC endpoints" in tool_def.description
        assert "endpoint" in tool_def.inputSchema["properties"]
        assert "method" in tool_def.inputSchema["properties"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_success(self, invoke_openrpc_tool, sample_openrpc_response):
        """Test successful invokeOpenRPC execution."""
        test_endpoint = "https://test-hotel.com/api/booking"

        respx.post(test_endpoint).mock(
            return_value=httpx.Response(
                200,
                json=sample_openrpc_response,
                headers={"content-type": "application/json"}
            )
        )

        result = await invoke_openrpc_tool.execute({
            "endpoint": test_endpoint,
            "method": "confirmBooking",
            "params": {"roomType": "standard"},
            "id": "test-123"
        })

        assert result["ok"] is True
        assert result["result"]["bookingId"] == "TEST-12345"
        assert result["raw"]["jsonrpc"] == "2.0"

    @pytest.mark.asyncio
    @respx.mock
    async def test_execute_rpc_error(self, invoke_openrpc_tool):
        """Test invokeOpenRPC with RPC error response."""
        test_endpoint = "https://test-hotel.com/api/booking"

        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": "Invalid params"
            },
            "id": "test-123"
        }

        respx.post(test_endpoint).mock(
            return_value=httpx.Response(
                200,
                json=error_response,
                headers={"content-type": "application/json"}
            )
        )

        result = await invoke_openrpc_tool.execute({
            "endpoint": test_endpoint,
            "method": "invalidMethod",
            "params": {},
        })

        assert result["ok"] is False
        assert result["error"]["code"] == "ANP_INVOCATION_FAILED"
        assert "Invalid params" in result["error"]["message"]