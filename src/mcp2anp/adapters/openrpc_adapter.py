"""OpenRPC adapter for JSON-RPC 2.0 communication."""

import json
import uuid
from typing import Any

import httpx
import structlog

from ..utils import LoggerMixin, models

logger = structlog.get_logger(__name__)


class OpenRPCAdapter(LoggerMixin):
    """Adapter for OpenRPC JSON-RPC 2.0 interactions."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize the OpenRPC adapter.

        Args:
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.timeout = timeout

    async def invoke_method(
        self,
        endpoint: str,
        method: str,
        params: dict[str, Any],
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> models.InvokeOpenRPCResponse:
        """Invoke an OpenRPC method.

        Args:
            endpoint: OpenRPC endpoint URL
            method: Method name to invoke
            params: Method parameters
            headers: Optional headers to include
            request_id: Optional request ID

        Returns:
            InvokeOpenRPCResponse with method result or error
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        self.log_operation(
            "Invoking OpenRPC method",
            endpoint=endpoint,
            method=method,
            request_id=request_id,
        )

        # Prepare JSON-RPC 2.0 request
        rpc_request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    json=rpc_request,
                    headers={
                        "Content-Type": "application/json",
                        **(headers or {}),
                    },
                )
                response.raise_for_status()

                try:
                    rpc_response = response.json()
                except json.JSONDecodeError as e:
                    self.log_operation(
                        "Invalid JSON response from OpenRPC endpoint",
                        level="error",
                        endpoint=endpoint,
                        method=method,
                        error=str(e),
                    )
                    return models.InvokeOpenRPCResponse(
                        ok=False,
                        error=models.ANPError(
                            code="ANP_INVALID_RESPONSE",
                            message="Invalid JSON response from server",
                        ),
                    )

                # Check for JSON-RPC errors
                if "error" in rpc_response:
                    rpc_error = rpc_response["error"]
                    self.log_operation(
                        "OpenRPC method returned error",
                        level="warning",
                        endpoint=endpoint,
                        method=method,
                        rpc_error=rpc_error,
                    )
                    return models.InvokeOpenRPCResponse(
                        ok=False,
                        error=models.ANPError(
                            code="ANP_INVOCATION_FAILED",
                            message=f"JSON-RPC error: {rpc_error.get('message', 'Unknown error')}",
                            raw=rpc_error,
                        ),
                    )

                # Extract result
                result = rpc_response.get("result")
                self.log_operation(
                    "OpenRPC method invoked successfully",
                    endpoint=endpoint,
                    method=method,
                    request_id=request_id,
                )

                return models.InvokeOpenRPCResponse(
                    ok=True,
                    result=result,
                    raw=rpc_response,
                )

        except httpx.HTTPStatusError as e:
            self.log_operation(
                "HTTP error invoking OpenRPC method",
                level="error",
                endpoint=endpoint,
                method=method,
                status_code=e.response.status_code,
                error=str(e),
            )
            return models.InvokeOpenRPCResponse(
                ok=False,
                error=models.ANPError(
                    code="ANP_HTTP_ERROR",
                    message=f"HTTP {e.response.status_code}: {str(e)}",
                ),
            )

        except httpx.RequestError as e:
            self.log_operation(
                "Request error invoking OpenRPC method",
                level="error",
                endpoint=endpoint,
                method=method,
                error=str(e),
            )
            return models.InvokeOpenRPCResponse(
                ok=False,
                error=models.ANPError(
                    code="ANP_REQUEST_ERROR",
                    message=str(e),
                ),
            )

        except Exception as e:
            self.log_operation(
                "Unexpected error invoking OpenRPC method",
                level="error",
                endpoint=endpoint,
                method=method,
                error=str(e),
            )
            return models.InvokeOpenRPCResponse(
                ok=False,
                error=models.ANPError(
                    code="ANP_UNKNOWN_ERROR",
                    message=str(e),
                ),
            )
