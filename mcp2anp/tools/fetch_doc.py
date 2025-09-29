"""FetchDoc tool implementation for MCP2ANP."""

from typing import Any

import structlog

from ..adapters import ANPClient
from ..auth import SessionManager
from ..utils import LoggerMixin, models

logger = structlog.get_logger(__name__)


class FetchDocTool(LoggerMixin):
    """Tool for fetching and parsing ANP documents."""

    def __init__(self, session_manager: SessionManager) -> None:
        """Initialize the FetchDoc tool.

        Args:
            session_manager: Session manager instance
        """
        super().__init__()
        self.session_manager = session_manager
        self.anp_client = ANPClient()


    async def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute the fetchDoc tool.

        Args:
            arguments: Tool arguments with url

        Returns:
            FetchDoc response with document content and links
        """
        try:
            # Validate arguments
            request = models.FetchDocRequest(**arguments)

            self.log_operation(
                "Executing fetchDoc tool",
                url=request.url,
            )

            # Get authentication headers if available
            auth_headers = self.session_manager.get_auth_headers(
                target_url=request.url,
            )

            # Fetch the document
            response = await self.anp_client.fetch_document(
                request.url,
                headers=auth_headers,
            )

            self.log_operation(
                "FetchDoc tool completed",
                url=request.url,
                success=response.ok,
                link_count=len(response.links) if response.links else 0,
            )

            # Convert response to dict for MCP compatibility
            return response.model_dump(by_alias=True, exclude_none=True)

        except Exception as e:
            self.log_operation(
                "FetchDoc tool execution failed",
                level="error",
                url=arguments.get("url", "unknown"),
                error=str(e),
            )
            return {
                "ok": False,
                "error": {
                    "code": "ANP_EXECUTION_ERROR",
                    "message": str(e),
                },
            }
