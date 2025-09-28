"""Session management for MCP2ANP server."""

from __future__ import annotations

from typing import Any, Dict

from ..utils import LoggerMixin
from .did_auth import DIDAuth


class SessionManager(LoggerMixin):
    """Manages authentication sessions and contexts."""

    def __init__(self) -> None:
        """Initialize the session manager."""
        super().__init__()
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._default_session = "default"
        self._did_auth = DIDAuth()

    async def set_auth_context(
        self,
        did_document_path: str,
        did_private_key_path: str,
        *,
        did_document: Dict[str, Any],
        private_key_pem: str,
        session_id: str | None = None,
    ) -> bool:
        """Set authentication context for a session.

        Args:
            did_document_path: Path to DID document file
            did_private_key_path: Path to DID private key file
            did_document: Parsed DID document content
            private_key_pem: Private key in PEM format
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
                "did_document": did_document,
                "private_key_pem": private_key_pem,
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

    def get_auth_context(self, session_id: str | None = None) -> Dict[str, Any] | None:
        """Get authentication context for a session.

        Args:
            session_id: Session identifier (uses default if None)

        Returns:
            Authentication context or None if not found
        """
        if session_id is None:
            session_id = self._default_session

        return self._sessions.get(session_id)

    def is_authenticated(self, session_id: str | None = None) -> bool:
        """Check if a session is authenticated.

        Args:
            session_id: Session identifier (uses default if None)

        Returns:
            True if session is authenticated
        """
        context = self.get_auth_context(session_id)
        return context is not None and context.get("authenticated", False)

    def clear_session(self, session_id: str | None = None) -> None:
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

    def get_auth_headers(
        self,
        session_id: str | None = None,
        *,
        target_url: str | None = None,
    ) -> dict[str, str]:
        """Get authentication headers for HTTP requests.

        Args:
            session_id: Session identifier (uses default if None)
            target_url: URL that will receive the authenticated request

        Returns:
            Dictionary of headers to include in requests
        """
        context = self.get_auth_context(session_id)
        if not context or not context.get("authenticated"):
            return {}

        did_document = context.get("did_document")
        private_key_pem = context.get("private_key_pem")
        if not did_document or not private_key_pem:
            self.log_operation(
                "Missing DID credentials",
                level="warning",
                session_id=session_id or self._default_session,
            )
            return {}

        try:
            token = self._did_auth.generate_auth_token(
                did_document,
                private_key_pem,
                target_url or did_document.get("id", ""),
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            self.log_operation(
                "Failed to generate auth token",
                level="error",
                session_id=session_id or self._default_session,
                error=str(exc),
            )
            return {}

        if not token:
            return {}

        did_id = did_document.get("id", "")

        headers: Dict[str, str] = {
            "User-Agent": "mcp2anp/0.1.0",
            "Authorization": f"DIDWBA {token}",
        }
        if did_id:
            headers["X-DID-Subject"] = did_id

        return headers
