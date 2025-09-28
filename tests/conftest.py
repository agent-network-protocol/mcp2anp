"""Pytest configuration and fixtures."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp2anp.auth import SessionManager
from mcp2anp.tools import FetchDocTool, InvokeOpenRPCTool, SetAuthTool


@pytest.fixture
def sample_did_document() -> dict[str, Any]:
    """Sample DID document for testing."""
    return {
        "id": "did:example:123456789abcdefghi",
        "verificationMethod": [
            {
                "id": "did:example:123456789abcdefghi#keys-1",
                "type": "RsaVerificationKey2018",
                "controller": "did:example:123456789abcdefghi",
                "publicKeyPem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----"
            }
        ],
        "authentication": [
            "did:example:123456789abcdefghi#keys-1"
        ]
    }


@pytest.fixture
def sample_private_key() -> str:
    """Generate a sample RSA private key for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return pem.decode('utf-8')


@pytest.fixture
def temp_did_files(sample_did_document, sample_private_key):
    """Create temporary DID document and private key files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create DID document file
        did_doc_path = temp_path / "did-document.json"
        with open(did_doc_path, 'w') as f:
            json.dump(sample_did_document, f)

        # Create private key file
        private_key_path = temp_path / "private-key.pem"
        with open(private_key_path, 'w') as f:
            f.write(sample_private_key)

        yield {
            "did_document_path": str(did_doc_path),
            "private_key_path": str(private_key_path),
        }


@pytest.fixture
def session_manager():
    """Create a session manager for testing."""
    return SessionManager()


@pytest.fixture
def set_auth_tool(session_manager):
    """Create a SetAuth tool instance for testing."""
    return SetAuthTool(session_manager)


@pytest.fixture
def fetch_doc_tool(session_manager):
    """Create a FetchDoc tool instance for testing."""
    return FetchDocTool(session_manager)


@pytest.fixture
def invoke_openrpc_tool(session_manager):
    """Create an InvokeOpenRPC tool instance for testing."""
    return InvokeOpenRPCTool(session_manager)


@pytest.fixture
def sample_anp_document() -> dict[str, Any]:
    """Sample ANP agent description document."""
    return {
        "protocolType": "ANP",
        "name": "Test Hotel Agent",
        "description": "A test hotel booking agent",
        "version": "1.0.0",
        "interfaces": [
            {
                "protocol": "openrpc",
                "url": "https://test-hotel.com/api/booking-interface.json",
                "title": "Booking Interface"
            }
        ],
        "informations": [
            {
                "url": "https://test-hotel.com/info/amenities.json",
                "title": "Hotel Amenities"
            }
        ]
    }


@pytest.fixture
def sample_openrpc_response() -> dict[str, Any]:
    """Sample OpenRPC success response."""
    return {
        "jsonrpc": "2.0",
        "result": {
            "bookingId": "TEST-12345",
            "status": "confirmed",
            "totalPrice": 299.99
        },
        "id": "test-request-123"
    }
