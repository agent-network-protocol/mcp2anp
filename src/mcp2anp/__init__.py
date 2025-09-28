"""MCP to ANP Bridge Server.

This package provides a Model Control Protocol (MCP) server that bridges
to Agent Network Protocol (ANP) agents.
"""

__version__ = "0.1.0"
__author__ = "mcp2anp Team"

# Avoid importing the server module at package level to prevent
# dependency issues during testing
__all__ = ["__version__", "__author__"]