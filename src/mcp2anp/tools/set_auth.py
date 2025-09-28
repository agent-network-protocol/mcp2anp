"""SetAuth tool implementation for MCP2ANP."""

from typing import Any, Dict

import structlog

from ..mcp_types import Tool

from ..auth import DIDAuth, SessionManager
from ..utils import LoggerMixin, models

logger = structlog.get_logger(__name__)


class SetAuthTool(LoggerMixin):
    """Tool for setting DID-based authentication context."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize the SetAuth tool.

        Args:
            session_manager: Session manager instance
        """
        super().__init__()
        self.session_manager = session_manager
        self.did_auth = DIDAuth()

    def get_tool_definition(self) -> Tool:
        """Get the MCP tool definition.

        Returns:
            Tool definition for anp.setAuth
        """
        return Tool(
            name="anp.setAuth",
            description=(
                "Set DID-based authentication context for ANP interactions. "
                "This stores local DID credentials that will be used for "
                "subsequent fetchDoc and invokeOpenRPC calls."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "didDocumentPath": {
                        "type": "string",
                        "description": "Path to the DID document JSON file",
                    },
                    "didPrivateKeyPath": {
                        "type": "string",
                        "description": "Path to the DID private key PEM file",
                    },
                },
                "required": ["didDocumentPath", "didPrivateKeyPath"],
            },
        )

    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the setAuth tool.

        Args:
            arguments: Tool arguments with didDocumentPath and didPrivateKeyPath

        Returns:
            Result indicating success or failure
        """
        try:
            # Validate arguments
            request = models.SetAuthRequest(**arguments)

            self.log_operation(
                "Executing setAuth tool",
                did_doc_path=request.did_document_path,
                private_key_path=request.did_private_key_path,
            )

            # Load and validate DID document
            did_document = await self.did_auth.load_did_document(
                request.did_document_path
            )
            if not did_document:
                return {
                    "ok": False,
                    "error": {
                        "code": "ANP_DID_LOAD_ERROR",
                        "message": "Failed to load or parse DID document",
                    },
                }

            # Load and validate private key
            private_key = await self.did_auth.load_private_key(
                request.did_private_key_path
            )
            if not private_key:
                return {
                    "ok": False,
                    "error": {
                        "code": "ANP_KEY_LOAD_ERROR",
                        "message": "Failed to load or validate private key",
                    },
                }

            # Set authentication context
            success = await self.session_manager.set_auth_context(
                request.did_document_path,
                request.did_private_key_path,
            )

            if success:
                self.log_operation(
                    "SetAuth tool completed successfully",
                    did_id=did_document.get("id", "unknown"),
                )
                return {"ok": True}
            else:
                return {
                    "ok": False,
                    "error": {
                        "code": "ANP_SESSION_ERROR",
                        "message": "Failed to set authentication context",
                    },
                }

        except Exception as e:
            self.log_operation(
                "SetAuth tool execution failed",
                level="error",
                error=str(e),
            )
            return {
                "ok": False,
                "error": {
                    "code": "ANP_EXECUTION_ERROR",
                    "message": str(e),
                },
            }