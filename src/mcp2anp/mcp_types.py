"""Simple MCP types implementation for testing purposes."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Tool(BaseModel):
    """MCP Tool definition."""

    name: str
    description: str
    inputSchema: Dict[str, Any]


class InitializationOptions(BaseModel):
    """MCP initialization options."""

    capabilities: Dict[str, Any] = {}


class MockMCPServer:
    """Mock MCP server for testing purposes."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: List[Tool] = []
        self._tool_handlers: Dict[str, Any] = {}
        self._list_tools_handler = None

    def list_tools(self):
        """Decorator for registering list_tools handler."""
        def decorator(func):
            self._list_tools_handler = func
            return func
        return decorator

    def call_tool(self):
        """Decorator for registering call_tool handler."""
        def decorator(func):
            self._tool_handlers["call_tool"] = func
            return func
        return decorator

    def create_initialization_options(self) -> InitializationOptions:
        """Create initialization options."""
        return InitializationOptions()

    async def run(self, read_stream, write_stream, options):
        """Mock run method."""
        print(f"Mock MCP server {self.name} would start here")
        return True