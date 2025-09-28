"""Unit tests for SessionManager."""

import pytest

from mcp2anp.auth import SessionManager


class TestSessionManager:
    """Test cases for SessionManager."""

    def test_init(self):
        """Test SessionManager initialization."""
        manager = SessionManager()
        assert manager._sessions == {}
        assert manager._default_session == "default"

    @pytest.mark.asyncio
    async def test_set_auth_context_success(self, sample_did_document, sample_private_key):
        """Test successful authentication context setting."""
        manager = SessionManager()

        result = await manager.set_auth_context(
            "test-did-doc.json",
            "test-private-key.pem",
            did_document=sample_did_document,
            private_key_pem=sample_private_key,
        )

        assert result is True
        assert manager.is_authenticated()

        context = manager.get_auth_context()
        assert context["did_document_path"] == "test-did-doc.json"
        assert context["did_private_key_path"] == "test-private-key.pem"
        assert context["did_document"]["id"] == sample_did_document["id"]
        assert context["authenticated"] is True

    @pytest.mark.asyncio
    async def test_set_auth_context_with_session_id(self, sample_did_document, sample_private_key):
        """Test setting auth context with specific session ID."""
        manager = SessionManager()

        result = await manager.set_auth_context(
            "test-did-doc.json",
            "test-private-key.pem",
            did_document=sample_did_document,
            private_key_pem=sample_private_key,
            session_id="custom-session",
        )

        assert result is True
        assert not manager.is_authenticated()  # default session not authenticated
        assert manager.is_authenticated("custom-session")

    def test_get_auth_context_not_found(self):
        """Test getting auth context when not set."""
        manager = SessionManager()

        context = manager.get_auth_context()
        assert context is None

        context = manager.get_auth_context("nonexistent")
        assert context is None

    def test_is_authenticated_false(self):
        """Test is_authenticated when not authenticated."""
        manager = SessionManager()
        assert not manager.is_authenticated()
        assert not manager.is_authenticated("nonexistent")

    def test_clear_session(self):
        """Test clearing session."""
        manager = SessionManager()
        manager._sessions["test"] = {"authenticated": True}

        manager.clear_session("test")
        assert "test" not in manager._sessions

    def test_get_auth_headers_no_auth(self):
        """Test getting auth headers when not authenticated."""
        manager = SessionManager()
        headers = manager.get_auth_headers()
        assert headers == {}

    @pytest.mark.asyncio
    async def test_get_auth_headers_with_auth(self, sample_did_document, sample_private_key):
        """Test getting auth headers when authenticated."""
        manager = SessionManager()
        await manager.set_auth_context(
            "test.json",
            "test.pem",
            did_document=sample_did_document,
            private_key_pem=sample_private_key,
        )

        headers = manager.get_auth_headers(target_url="https://example.org/resource")
        assert headers["User-Agent"].startswith("mcp2anp/")
        assert headers["Authorization"].startswith("DIDWBA ")
        assert headers["X-DID-Subject"] == sample_did_document["id"]
