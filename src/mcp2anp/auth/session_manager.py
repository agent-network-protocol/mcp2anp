"""Session management for MCP2ANP server."""

import asyncio
from typing import Dict, Optional

import structlog

from ..utils import LoggerMixin

logger = structlog.get_logger(__name__)


class SessionManager(LoggerMixin):
    """Manages authentication sessions and contexts."""

    def __init__(self) -> None:
        """Initialize the session manager."""
        super().__init__()
        self._sessions: Dict[str, Dict] = {}
        self._default_session = "default"

    async def set_auth_context(
        self,
        did_document_path: str,
        did_private_key_path: str,
        session_id: str = None,
    ) -> bool:
        """Set authentication context for a session.

        Args:
            did_document_path: Path to DID document file
            did_private_key_path: Path to DID private key file
            session_id: Session identifier (uses default if None)

        Returns:
            True if authentication context was set successfully
        """
        if session_id is None:
            session_id = self._default_session

        try:
            self.log_operation(
                "Setting auth context",
                session_id=session_id,
                did_doc_path=did_document_path,
            )

            # Store auth context
            self._sessions[session_id] = {
                "did_document_path": did_document_path,
                "did_private_key_path": did_private_key_path,
                "authenticated": True,
            }

            self.log_operation(
                "Auth context set successfully",
                session_id=session_id,
            )
            return True

        except Exception as e:
            self.log_operation(
                "Failed to set auth context",
                level="error",
                session_id=session_id,
                error=str(e),
            )
            return False

    def get_auth_context(self, session_id: str = None) -> Optional[Dict]:
        """Get authentication context for a session.

        Args:
            session_id: Session identifier (uses default if None)

        Returns:
            Authentication context or None if not found
        """
        if session_id is None:
            session_id = self._default_session

        return self._sessions.get(session_id)

    def is_authenticated(self, session_id: str = None) -> bool:
        """Check if a session is authenticated.

        Args:
            session_id: Session identifier (uses default if None)

        Returns:
            True if session is authenticated
        """
        context = self.get_auth_context(session_id)
        return context is not None and context.get("authenticated", False)

    def clear_session(self, session_id: str = None) -> None:
        """Clear a session's authentication context.

        Args:
            session_id: Session identifier (uses default if None)
        """
        if session_id is None:
            session_id = self._default_session

        if session_id in self._sessions:
            del self._sessions[session_id]
            self.log_operation(
                "Session cleared",
                session_id=session_id,
            )

    def get_auth_headers(self, session_id: str = None) -> Dict[str, str]:
        """Get authentication headers for HTTP requests.

        Args:
            session_id: Session identifier (uses default if None)

        Returns:
            Dictionary of headers to include in requests
        """
        context = self.get_auth_context(session_id)
        if not context:
            return {}

        # For now, return empty headers - actual DID auth implementation
        # would generate appropriate authorization headers here
        return {
            "X-DID-Auth": "enabled",
            "User-Agent": "mcp2anp/0.1.0",
        }