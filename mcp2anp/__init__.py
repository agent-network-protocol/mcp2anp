"""MCP2ANP - MCP to ANP Protocol Bridge.

This package provides a Model Control Protocol (MCP) server that bridges
to Agent Network Protocol (ANP) agents using the agent-connect library.
"""

__version__ = "0.1.0"
__author__ = "mcp2anp Team"
__description__ = "MCP server that converts MCP protocol to ANP protocol"

# Export session management classes for external use
from .session import SessionConfig, SessionManager, SessionState

# Avoid importing the server module at package level to prevent
# dependency issues during testing
__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "SessionConfig",
    "SessionState",
    "SessionManager",
]
