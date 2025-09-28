"""DID-based authentication for ANP integration."""

import json
from pathlib import Path
from typing import Dict, Optional

import structlog
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from ..utils import LoggerMixin

logger = structlog.get_logger(__name__)


class DIDAuth(LoggerMixin):
    """DID-based authentication handler."""

    def __init__(self) -> None:
        """Initialize the DID authentication handler."""
        super().__init__()

    async def load_did_document(self, did_document_path: str) -> Optional[Dict]:
        """Load and parse a DID document.

        Args:
            did_document_path: Path to the DID document JSON file

        Returns:
            Parsed DID document or None if loading failed
        """
        try:
            path = Path(did_document_path)
            if not path.exists():
                self.log_operation(
                    "DID document not found",
                    level="error",
                    path=did_document_path,
                )
                return None

            with open(path, "r", encoding="utf-8") as f:
                did_doc = json.load(f)

            self.log_operation(
                "DID document loaded successfully",
                did_id=did_doc.get("id", "unknown"),
            )
            return did_doc

        except Exception as e:
            self.log_operation(
                "Failed to load DID document",
                level="error",
                path=did_document_path,
                error=str(e),
            )
            return None

    async def load_private_key(self, private_key_path: str) -> Optional[str]:
        """Load a private key from file.

        Args:
            private_key_path: Path to the private key PEM file

        Returns:
            Private key content or None if loading failed
        """
        try:
            path = Path(private_key_path)
            if not path.exists():
                self.log_operation(
                    "Private key file not found",
                    level="error",
                    path=private_key_path,
                )
                return None

            with open(path, "rb") as f:
                private_key_bytes = f.read()

            # Validate that it's a valid private key
            try:
                serialization.load_pem_private_key(
                    private_key_bytes,
                    password=None,
                )
            except Exception as key_error:
                self.log_operation(
                    "Invalid private key format",
                    level="error",
                    path=private_key_path,
                    error=str(key_error),
                )
                return None

            self.log_operation(
                "Private key loaded successfully",
                path=private_key_path,
            )
            return private_key_bytes.decode("utf-8")

        except Exception as e:
            self.log_operation(
                "Failed to load private key",
                level="error",
                path=private_key_path,
                error=str(e),
            )
            return None

    async def generate_auth_token(
        self,
        did_document: Dict,
        private_key: str,
        target_url: str,
    ) -> Optional[str]:
        """Generate an authentication token for a request.

        Args:
            did_document: The DID document
            private_key: The private key in PEM format
            target_url: The target URL being accessed

        Returns:
            Authentication token or None if generation failed
        """
        try:
            # This is a simplified implementation
            # In a real implementation, this would generate a proper
            # DIDWBA (DID Web-Based Authentication) token

            did_id = did_document.get("id", "unknown")
            self.log_operation(
                "Generating auth token",
                did_id=did_id,
                target_url=target_url,
            )

            # For MVP, return a placeholder token
            # Real implementation would involve:
            # 1. Creating a JWT with appropriate claims
            # 2. Signing with the private key
            # 3. Including DID verification information

            token = f"did-auth-{did_id}-{hash(target_url) % 10000}"

            self.log_operation(
                "Auth token generated",
                did_id=did_id,
                token_prefix=token[:20] + "...",
            )

            return token

        except Exception as e:
            self.log_operation(
                "Failed to generate auth token",
                level="error",
                error=str(e),
            )
            return None