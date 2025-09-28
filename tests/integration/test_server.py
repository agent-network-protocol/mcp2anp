"""Integration tests for MCP server."""

import pytest
import respx
import httpx

from mcp2anp.server import MCPServer


class TestMCPServer:
    """Integration tests for MCPServer."""

    def test_server_initialization(self):
        """Test server initializes correctly."""
        server = MCPServer()

        assert server.server is not None
        assert server.session_manager is not None
        assert server.fetch_doc_tool is not None
        assert server.invoke_openrpc_tool is not None
        assert server.set_auth_tool is not None

    def test_tool_definitions(self):
        """Test that all tools are properly defined."""
        server = MCPServer()

        # Test individual tool definitions
        set_auth_def = server.set_auth_tool.get_tool_definition()
        assert set_auth_def.name == "anp.setAuth"

        fetch_doc_def = server.fetch_doc_tool.get_tool_definition()
        assert fetch_doc_def.name == "anp.fetchDoc"

        invoke_rpc_def = server.invoke_openrpc_tool.get_tool_definition()
        assert invoke_rpc_def.name == "anp.invokeOpenRPC"

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_workflow(self, temp_did_files):
        """Test complete server workflow with all tools."""
        server = MCPServer()

        # Step 1: Set authentication
        auth_result = await server.set_auth_tool.execute({
            "didDocumentPath": temp_did_files["did_document_path"],
            "didPrivateKeyPath": temp_did_files["private_key_path"],
        })
        assert auth_result["ok"] is True

        # Step 2: Fetch ANP document
        test_anp_doc = {
            "protocolType": "ANP",
            "name": "Test Agent",
            "interfaces": [{
                "protocol": "openrpc",
                "url": "https://test.com/api/rpc"
            }]
        }

        respx.get("https://test.com/agent.json").mock(
            return_value=httpx.Response(
                200,
                json=test_anp_doc,
                headers={"content-type": "application/json"}
            )
        )

        fetch_result = await server.fetch_doc_tool.execute({
            "url": "https://test.com/agent.json"
        })
        assert fetch_result["ok"] is True
        assert len(fetch_result["links"]) > 0

        # Step 3: Invoke OpenRPC method
        rpc_response = {
            "jsonrpc": "2.0",
            "result": {"status": "success"},
            "id": "test"
        }

        respx.post("https://test.com/api/rpc").mock(
            return_value=httpx.Response(
                200,
                json=rpc_response,
                headers={"content-type": "application/json"}
            )
        )

        invoke_result = await server.invoke_openrpc_tool.execute({
            "endpoint": "https://test.com/api/rpc",
            "method": "testMethod",
            "params": {"test": "value"}
        })
        assert invoke_result["ok"] is True
        assert invoke_result["result"]["status"] == "success"