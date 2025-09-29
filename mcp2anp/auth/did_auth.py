"""DID-based authentication for ANP integration."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path

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

    async def load_did_document(self, did_document_path: str) -> dict | None:
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

            with open(path, encoding="utf-8") as f:
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

    async def load_private_key(self, private_key_path: str) -> str | None:
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

    def generate_auth_token(
        self,
        did_document: dict,
        private_key: str,
        target_url: str,
    ) -> str | None:
        """Generate an authentication token for a request.

        Args:
            did_document: The DID document
            private_key: The private key in PEM format
            target_url: The target URL being accessed

        Returns:
            Authentication token or None if generation failed
        """
        try:
            did_id = did_document.get("id", "")
            self.log_operation(
                "Generating auth token",
                did_id=did_id or "unknown",
                target_url=target_url,
            )

            # Prepare JWT-style header and payload
            header = {"alg": "RS256", "typ": "DIDWBA"}
            issued_at = int(time.time())
            payload = {
                "iss": did_id,
                "sub": did_id,
                "aud": target_url,
                "iat": issued_at,
                "exp": issued_at + 300,
            }

            header_segment = self._b64url(
                json.dumps(header, separators=(",", ":")).encode("utf-8")
            )
            payload_segment = self._b64url(
                json.dumps(payload, separators=(",", ":")).encode("utf-8")
            )
            signing_input = f"{header_segment}.{payload_segment}".encode()

            private_key_obj = serialization.load_pem_private_key(
                private_key.encode("utf-8"),
                password=None,
            )

            signature = private_key_obj.sign(
                signing_input,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            signature_segment = self._b64url(signature)

            token = f"{header_segment}.{payload_segment}.{signature_segment}"

            self.log_operation(
                "Auth token generated",
                did_id=did_id or "unknown",
                token_prefix=token[:24] + "...",
            )

            return token

        except Exception as e:
            self.log_operation(
                "Failed to generate auth token",
                level="error",
                error=str(e),
            )
            return None

    @staticmethod
    def _b64url(data: bytes) -> str:
        """Return URL-safe base64 string without padding."""

        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")
