"""HTTP client for ANP interactions."""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List
from urllib.parse import urljoin

import httpx
import structlog

from ..utils import LoggerMixin, models

logger = structlog.get_logger(__name__)


class ANPClient(LoggerMixin):
    """HTTP client for ANP document fetching and parsing."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the ANP client.

        Args:
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.timeout = timeout

    async def fetch_document(
        self,
        url: str,
        headers: Dict[str, str] | None = None,
    ) -> models.FetchDocResponse:
        """Fetch and parse an ANP document.

        Args:
            url: URL to fetch
            headers: Optional headers to include

        Returns:
            FetchDocResponse with document content and extracted links
        """
        self.log_operation(
            "Fetching ANP document",
            url=url,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers or {})
                response.raise_for_status()

                content_type = response.headers.get("content-type", "application/octet-stream")
                raw_bytes = response.content
                detected_encoding = response.encoding or "utf-8"
                is_textual = self._is_textual_content(content_type)

                if is_textual:
                    text_content = raw_bytes.decode(detected_encoding, errors="replace")
                    content_encoding = detected_encoding
                else:
                    text_content = base64.b64encode(raw_bytes).decode("ascii")
                    content_encoding = "base64"

                self.log_operation(
                    "Document fetched successfully",
                    url=url,
                    content_type=content_type,
                    content_length=len(raw_bytes),
                    encoding=content_encoding,
                )

                # Parse JSON if applicable
                json_content = None
                if "json" in content_type.lower():
                    try:
                        json_content = response.json()
                    except json.JSONDecodeError as error:
                        self.log_operation(
                            "Failed to parse JSON content",
                            level="warning",
                            url=url,
                            error=str(error),
                        )

                # Extract links
                links = self._extract_links(json_content, url)

                return models.FetchDocResponse(
                    ok=True,
                    content_type=content_type,
                    encoding=content_encoding,
                    text=text_content,
                    json=json_content,
                    links=links,
                )

        except httpx.HTTPStatusError as e:
            self.log_operation(
                "HTTP error fetching document",
                level="error",
                url=url,
                status_code=e.response.status_code,
                error=str(e),
            )
            return models.FetchDocResponse(
                ok=False,
                error=models.ANPError(
                    code="ANP_HTTP_ERROR",
                    message=f"HTTP {e.response.status_code}: {str(e)}",
                ),
            )

        except httpx.RequestError as e:
            self.log_operation(
                "Request error fetching document",
                level="error",
                url=url,
                error=str(e),
            )
            return models.FetchDocResponse(
                ok=False,
                error=models.ANPError(
                    code="ANP_REQUEST_ERROR",
                    message=str(e),
                ),
            )

        except Exception as e:
            self.log_operation(
                "Unexpected error fetching document",
                level="error",
                url=url,
                error=str(e),
            )
            return models.FetchDocResponse(
                ok=False,
                error=models.ANPError(
                    code="ANP_UNKNOWN_ERROR",
                    message=str(e),
                ),
            )

    def _extract_links(
        self,
        json_content: Dict[str, Any] | None,
        base_url: str,
    ) -> List[Dict[str, str]]:
        """Extract followable links from ANP JSON content.

        Args:
            json_content: Parsed JSON content
            base_url: Base URL for resolving relative links

        Returns:
            List of link information dictionaries
        """
        if not json_content:
            return []

        links: List[Dict[str, str]] = []

        try:
            # Extract from interfaces array
            interfaces = json_content.get("interfaces", [])
            for interface in interfaces:
                if isinstance(interface, dict):
                    url = interface.get("url")
                    if url:
                        links.append({
                            "rel": "interface",
                            "url": self._resolve_url(url, base_url),
                            "protocol": interface.get("protocol", "unknown"),
                            "title": interface.get("title", ""),
                        })

            # Extract from informations array
            informations = json_content.get("informations", [])
            for info in informations:
                if isinstance(info, dict):
                    url = info.get("url")
                    if url:
                        links.append({
                            "rel": "info",
                            "url": self._resolve_url(url, base_url),
                            "title": info.get("title", ""),
                        })

            # Extract from other common link fields
            for field in ["schema", "documentation", "examples"]:
                if field in json_content:
                    field_value = json_content[field]
                    if isinstance(field_value, str) and field_value.startswith("http"):
                        links.append({
                            "rel": field,
                            "url": self._resolve_url(field_value, base_url),
                        })
                    elif isinstance(field_value, dict) and "url" in field_value:
                        links.append({
                            "rel": field,
                            "url": self._resolve_url(field_value["url"], base_url),
                            "title": field_value.get("title", ""),
                        })

            self.log_operation(
                "Links extracted",
                base_url=base_url,
                link_count=len(links),
            )

        except Exception as e:
            self.log_operation(
                "Error extracting links",
                level="warning",
                base_url=base_url,
                error=str(e),
            )

        return links

    def _resolve_url(self, url: str, base_url: str) -> str:
        """Resolve a potentially relative URL against a base URL.

        Args:
            url: URL to resolve
            base_url: Base URL

        Returns:
            Resolved absolute URL
        """
        if url.startswith(("http://", "https://")):
            return url
        return urljoin(base_url, url)

    @staticmethod
    def _is_textual_content(content_type: str) -> bool:
        """Determine whether the given content type should be treated as text."""

        lowered = content_type.lower()
        if lowered.startswith("text/"):
            return True

        for token in ("json", "yaml", "xml", "+json", "+yaml"):
            if token in lowered:
                return True
        return False
