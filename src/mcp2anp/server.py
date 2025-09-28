"""MCP server implementation for ANP bridge."""

import asyncio
from typing import Any

import click
import structlog

from .auth import SessionManager
from .mcp_types import MockMCPServer as Server
from .mcp_types import Tool
from .tools import FetchDocTool, InvokeOpenRPCTool, SetAuthTool
from .utils import setup_logging

logger = structlog.get_logger(__name__)


class MCPServer:
    """MCP server that provides ANP bridge functionality."""

    def __init__(self) -> None:
        """Initialize the MCP server."""
        self.server = Server("mcp2anp")
        self.session_manager = SessionManager()

        # Initialize tools
        self.fetch_doc_tool = FetchDocTool(self.session_manager)
        self.invoke_openrpc_tool = InvokeOpenRPCTool(self.session_manager)
        self.set_auth_tool = SetAuthTool(self.session_manager)

        self._register_tools()
        self._register_handlers()

    def _register_tools(self) -> None:
        """Register MCP tools."""
        tools = [
            self.fetch_doc_tool.get_tool_definition(),
            self.invoke_openrpc_tool.get_tool_definition(),
            self.set_auth_tool.get_tool_definition(),
        ]

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            return tools

    def _register_handlers(self) -> None:
        """Register tool handlers."""

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
            """Handle tool calls."""
            logger.info("Tool called", tool_name=name, args=arguments)

            try:
                if name == "anp.setAuth":
                    return await self.set_auth_tool.execute(arguments)
                elif name == "anp.fetchDoc":
                    return await self.fetch_doc_tool.execute(arguments)
                elif name == "anp.invokeOpenRPC":
                    return await self.invoke_openrpc_tool.execute(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
            except Exception as e:
                logger.error("Tool execution failed", tool_name=name, error=str(e))
                return {
                    "ok": False,
                    "error": {
                        "code": "EXECUTION_ERROR",
                        "message": str(e)
                    }
                }

    async def run_stdio(self) -> None:
        """Run the server using stdio transport."""
        # Mock implementation for testing
        logger.info("Starting MCP server in stdio mode")
        await self.server.run(None, None, self.server.create_initialization_options())


@click.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Set the logging level",
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable hot reload for development",
)
def main(log_level: str, reload: bool) -> None:
    """Run the MCP2ANP bridge server."""
    setup_logging(log_level)

    if reload:
        logger.info("Starting MCP2ANP server with hot reload enabled")
    else:
        logger.info("Starting MCP2ANP server")

    server = MCPServer()

    try:
        asyncio.run(server.run_stdio())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main()
