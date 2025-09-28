"""InvokeOpenRPC tool implementation for MCP2ANP."""

from typing import Any

import structlog

from ..adapters import OpenRPCAdapter
from ..auth import SessionManager
from ..mcp_types import Tool
from ..utils import LoggerMixin, models

logger = structlog.get_logger(__name__)


class InvokeOpenRPCTool(LoggerMixin):
    """Tool for invoking OpenRPC methods via JSON-RPC 2.0."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize the InvokeOpenRPC tool.

        Args:
            session_manager: Session manager instance
        """
        super().__init__()
        self.session_manager = session_manager
        self.openrpc_adapter = OpenRPCAdapter()

    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition.

        Returns:
            Tool definition for anp.invokeOpenRPC
        """
        return Tool(
            name="anp.invokeOpenRPC",
            description=(
                "Invoke methods on OpenRPC endpoints using JSON-RPC 2.0 protocol. "
                "This tool handles structured interactions with ANP agents that "
                "expose OpenRPC interfaces."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "OpenRPC endpoint URL",
                        "format": "uri",
                    },
                    "method": {
                        "type": "string",
                        "description": "Name of the RPC method to invoke",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters to pass to the method",
                        "default": {},
                    },
                    "id": {
                        "type": "string",
                        "description": "Optional request ID for tracking",
                    },
                },
                "required": ["endpoint", "method"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the invokeOpenRPC tool.

        Args:
            arguments: Tool arguments with endpoint, method, params, and optional id

        Returns:
            InvokeOpenRPC response with method result or error
        """
        try:
            # Validate arguments
            request = models.InvokeOpenRPCRequest(**arguments)

            self.log_operation(
                "Executing invokeOpenRPC tool",
                endpoint=request.endpoint,
                method=request.method,
                request_id=request.id,
            )

            # Get authentication headers if available
            auth_headers = self.session_manager.get_auth_headers(
                target_url=request.endpoint,
            )

            # Invoke the OpenRPC method
            response = await self.openrpc_adapter.invoke_method(
                endpoint=request.endpoint,
                method=request.method,
                params=request.params,
                headers=auth_headers,
                request_id=request.id,
            )

            self.log_operation(
                "InvokeOpenRPC tool completed",
                endpoint=request.endpoint,
                method=request.method,
                success=response.ok,
                request_id=request.id,
            )

            # Convert response to dict for MCP compatibility
            return response.model_dump(by_alias=True, exclude_none=True)

        except Exception as e:
            self.log_operation(
                "InvokeOpenRPC tool execution failed",
                level="error",
                endpoint=arguments.get("endpoint", "unknown"),
                method=arguments.get("method", "unknown"),
                error=str(e),
            )
            return {
                "ok": False,
                "error": {
                    "code": "ANP_EXECUTION_ERROR",
                    "message": str(e),
                },
            }
