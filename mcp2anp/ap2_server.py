"""MCP server implementation for AP2 payment flow (本地 stdio 模式)。"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import click
import mcp.server.stdio
import structlog
from aiohttp import ClientSession
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from mcp.server import Server
from mcp.types import TextContent, Tool
from pydantic import BaseModel, Field

from anp.ap2 import (
    ANPMessage,
    CartMandate,
    CartMandateRequestData,
    DisplayItem,
    MoneyAmount,
    PaymentDetailsTotal,
    PaymentMandateContents,
    PaymentResponse,
    PaymentResponseDetails,
    ShippingAddress,
)
from anp.ap2.cart_mandate import validate_cart_mandate
from anp.ap2.payment_mandate import build_payment_mandate, validate_payment_mandate
from anp.ap2.utils import compute_hash
from anp.authentication.did_wba_authenticator import DIDWbaAuthHeader
from anp.authentication.verification_methods import EcdsaSecp256k1VerificationKey2019

from .utils import setup_logging

logger = structlog.get_logger(__name__)

mcp_instructions = """这是一个AP2支付流程的MCP服务器，通过这个服务器，你可以完成AP2支付流程：
- 创建购物车授权请求 (CartMandateRequest)
- 发送支付授权 (PaymentMandate)

AP2支付流程包括：
1. 使用 ap2.createCartMandate 创建购物车授权请求并发送给商户服务器
2. 验证返回的 CartMandate
3. 使用 ap2.sendPaymentMandate 构建并发送 PaymentMandate 完成支付流程

所有AP2支付相关的操作，必须使用mcp2anp的tools进行处理。
"""

# 创建 MCP Server 实例
server = Server("mcp2anp-ap2", instructions=mcp_instructions)

# 全局状态：AP2Handler 实例（在启动时初始化）
ap2_handler: AP2Handler | None = None


def get_project_root() -> Path:
    """获取项目根目录。"""
    return Path(__file__).resolve().parents[1]


def load_text(path: Path) -> str:
    """加载文本文件。"""
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    """加载JSON文件。"""
    return json.loads(load_text(path))


def public_key_from_did_document(did_document: dict) -> str:
    """从DID文档中提取secp256k1公钥PEM。"""
    method = did_document["verificationMethod"][0]
    verifier = EcdsaSecp256k1VerificationKey2019.from_dict(method)
    return verifier.public_key.public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


class CreateCartMandateRequest(BaseModel):
    """创建购物车授权请求的参数。"""

    merchant_url: str = Field(..., description="商户服务器URL")
    merchant_did: str = Field(..., description="商户DID")
    merchant_public_key: str = Field(
        ..., description="商户公钥PEM（必需，用于验证merchant server返回的签名）"
    )
    cart_mandate_id: str = Field(..., description="购物车授权ID")
    items: list[dict[str, Any]] = Field(..., description="商品列表")
    shipping_address: dict[str, Any] = Field(..., description="配送地址")
    remark: str | None = Field(None, description="备注")


class SendPaymentMandateRequest(BaseModel):
    """发送支付授权请求的参数。"""

    merchant_url: str = Field(..., description="商户服务器URL")
    merchant_did: str = Field(..., description="商户DID")
    merchant_public_key: str = Field(
        ..., description="商户公钥PEM（必需，用于验证merchant server返回的签名）"
    )
    cart_mandate_id: str = Field(..., description="购物车授权ID")
    payment_mandate_id: str = Field(..., description="支付授权ID")
    refund_period: int = Field(30, description="退款期限（天）")


class AP2Handler:
    """AP2支付流程处理类（作为客户端调用merchant server）。"""

    def __init__(
        self,
        did_document_path: str,
        private_key_path: str,
        client_did: str,
        payment_private_key: str,
        shopper_public_key: str,
    ):
        self.auth_handler = DIDWbaAuthHeader(
            did_document_path=did_document_path,
            private_key_path=private_key_path,
        )
        self.client_did = client_did
        self.payment_private_key = payment_private_key
        self.shopper_public_key = shopper_public_key
        self.cart_mandates: dict[str, CartMandate] = {}
        # 缓存 merchant 公钥（从 merchant_did 解析）
        self.merchant_public_keys: dict[str, str] = {}

    def _get_merchant_public_key(
        self, merchant_did: str, provided_key: str | None = None
    ) -> str:
        """获取商户公钥（从参数或缓存）。"""
        if provided_key:
            # 如果提供了公钥，缓存它
            self.merchant_public_keys[merchant_did] = provided_key
            return provided_key

        # 检查缓存
        if merchant_did in self.merchant_public_keys:
            return self.merchant_public_keys[merchant_did]

        raise ValueError(
            f"Merchant public key not found for {merchant_did}. "
            "Please provide merchant_public_key parameter in the tool call."
        )

    async def handle_create_cart_mandate(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """处理创建购物车授权请求。"""
        try:
            request = CreateCartMandateRequest(**arguments)
            logger.info(
                "Creating cart mandate",
                merchant_url=request.merchant_url,
                cart_mandate_id=request.cart_mandate_id,
            )

            # 构建购物车授权请求数据
            display_items = [
                DisplayItem(
                    id=item["id"],
                    quantity=item["quantity"],
                    amount=MoneyAmount(
                        currency=item.get("currency", "CNY"),
                        value=item.get("price", 299.99),
                    ),
                    label=item.get("label", f"Product {item['id']}"),
                    options=item.get("options"),
                    remark=item.get("remark"),
                )
                for item in request.items
            ]

            request_data = CartMandateRequestData(
                cart_mandate_id=request.cart_mandate_id,
                items=display_items,
                shipping_address=ShippingAddress(**request.shipping_address),
                remark=request.remark,
            )

            message = ANPMessage(
                messageId=f"cart-request-{request.cart_mandate_id}",
                from_=self.client_did,
                to=request.merchant_did,
                data=request_data,
            )

            # 发送请求到商户服务器
            async with ClientSession(trust_env=False) as session:
                auth_header = self.auth_handler.get_auth_header(
                    request.merchant_url, force_new=True
                )
                async with session.post(
                    f"{request.merchant_url}/ap2/merchant/create_cart_mandate",
                    json=message.model_dump(by_alias=True, exclude_none=True),
                    headers=auth_header,
                ) as response:
                    response.raise_for_status()
                    self.auth_handler.update_token(
                        request.merchant_url, dict(response.headers)
                    )
                    cart_response = await response.json()

            # 验证返回的CartMandate
            received_cart = CartMandate(**cart_response["data"])
            merchant_public_key = self._get_merchant_public_key(
                request.merchant_did, request.merchant_public_key
            )
            validate_cart_mandate(
                cart_mandate=received_cart,
                merchant_public_key=merchant_public_key,
                merchant_algorithm="ES256K",
                expected_shopper_did=self.client_did,
            )
            cart_hash = compute_hash(
                received_cart.contents.model_dump(exclude_none=True)
            )

            # 存储购物车授权
            self.cart_mandates[request.cart_mandate_id] = received_cart

            logger.info(
                "Cart mandate created successfully",
                cart_mandate_id=request.cart_mandate_id,
                cart_hash=cart_hash[:32],
            )

            return {
                "ok": True,
                "cart_mandate_id": request.cart_mandate_id,
                "cart_mandate": received_cart.model_dump(exclude_none=True),
                "cart_hash": cart_hash,
            }

        except Exception as e:
            logger.error(
                "Failed to create cart mandate",
                error=str(e),
                exc_info=True,
            )
            return {
                "ok": False,
                "error": {
                    "code": "CART_MANDATE_ERROR",
                    "message": str(e),
                },
            }

    async def handle_send_payment_mandate(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """处理发送支付授权请求。"""
        try:
            request = SendPaymentMandateRequest(**arguments)
            logger.info(
                "Sending payment mandate",
                merchant_url=request.merchant_url,
                payment_mandate_id=request.payment_mandate_id,
            )

            # 获取之前创建的购物车授权
            cart_mandate = self.cart_mandates.get(request.cart_mandate_id)
            if not cart_mandate:
                return {
                    "ok": False,
                    "error": {
                        "code": "CART_MANDATE_NOT_FOUND",
                        "message": f"Cart mandate {request.cart_mandate_id} not found. Please create it first.",
                    },
                }

            cart_hash = compute_hash(
                cart_mandate.contents.model_dump(exclude_none=True)
            )

            # 构建支付响应
            payment_response = PaymentResponse(
                request_id=cart_mandate.contents.payment_request.details.id,
                method_name="QR_CODE",
                details=PaymentResponseDetails(
                    channel=cart_mandate.contents.payment_request.method_data[
                        0
                    ].data.channel,
                    out_trade_no=cart_mandate.contents.payment_request.method_data[
                        0
                    ].data.out_trade_no,
                ),
            )

            # 构建支付授权内容
            contents = PaymentMandateContents(
                payment_mandate_id=request.payment_mandate_id,
                payment_details_id=cart_mandate.contents.payment_request.details.id,
                payment_details_total=PaymentDetailsTotal(
                    label="Total",
                    amount=cart_mandate.contents.payment_request.details.total.amount,
                    refund_period=request.refund_period,
                ),
                payment_response=payment_response,
                merchant_agent="MerchantAgent",
                cart_hash=cart_hash,
            )

            # 构建支付授权
            payment_mandate = build_payment_mandate(
                contents=contents,
                user_private_key=self.payment_private_key,
                user_did=self.client_did,
                user_kid="shopper-key-001",
                merchant_did=request.merchant_did,
                algorithm="ES256K",
            )

            # 验证支付授权
            validate_payment_mandate(
                payment_mandate=payment_mandate,
                shopper_public_key=self.shopper_public_key,
                shopper_algorithm="ES256K",
                expected_merchant_did=request.merchant_did,
                expected_cart_hash=cart_hash,
            )

            # 发送支付授权到商户服务器
            payment_message = ANPMessage(
                messageId=f"payment-request-{request.payment_mandate_id}",
                from_=self.client_did,
                to=request.merchant_did,
                data=payment_mandate,
            )

            auth_header = self.auth_handler.get_auth_header(request.merchant_url)
            async with ClientSession(trust_env=False) as session:
                async with session.post(
                    f"{request.merchant_url}/ap2/merchant/send_payment_mandate",
                    json=payment_message.model_dump(by_alias=True, exclude_none=True),
                    headers=auth_header,
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

            logger.info(
                "Payment mandate sent successfully",
                payment_mandate_id=request.payment_mandate_id,
                status=result.get("data", {}).get("status"),
            )

            return {
                "ok": True,
                "payment_mandate_id": request.payment_mandate_id,
                "status": result.get("data", {}).get("status"),
                "payment_id": result.get("data", {}).get("payment_id"),
                "message": result.get("data", {}).get("message"),
                "payment_receipt": result.get("data", {}).get("payment_receipt"),
                "fulfillment_receipt": result.get("data", {}).get("fulfillment_receipt"),
            }

        except Exception as e:
            logger.error(
                "Failed to send payment mandate",
                error=str(e),
                exc_info=True,
            )
            return {
                "ok": False,
                "error": {
                    "code": "PAYMENT_MANDATE_ERROR",
                    "message": str(e),
                },
            }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """返回可用工具列表。"""
    return [
        Tool(
            name="ap2.createCartMandate",
            description=(
                "创建购物车授权请求并发送给商户服务器。"
                "此工具会构建CartMandateRequest，发送给商户，验证返回的CartMandate，并存储购物车授权信息。"
                "返回购物车授权详情和cart_hash，用于后续的支付授权。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "merchant_url": {
                        "type": "string",
                        "description": "商户服务器URL",
                        "format": "uri",
                    },
                    "merchant_did": {
                        "type": "string",
                        "description": "商户DID",
                    },
                    "merchant_public_key": {
                        "type": "string",
                        "description": "商户公钥PEM（必需，用于验证merchant server返回的签名）",
                    },
                    "cart_mandate_id": {
                        "type": "string",
                        "description": "购物车授权ID（唯一标识）",
                    },
                    "items": {
                        "type": "array",
                        "description": "商品列表",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "quantity": {"type": "integer"},
                                "price": {"type": "number"},
                                "currency": {"type": "string", "default": "CNY"},
                                "label": {"type": "string"},
                                "options": {"type": "object"},
                                "remark": {"type": "string"},
                            },
                            "required": ["id", "quantity"],
                        },
                    },
                    "shipping_address": {
                        "type": "object",
                        "description": "配送地址",
                        "properties": {
                            "recipient_name": {"type": "string"},
                            "phone": {"type": "string"},
                            "region": {"type": "string"},
                            "city": {"type": "string"},
                            "address_line": {"type": "string"},
                            "postal_code": {"type": "string"},
                        },
                        "required": [
                            "recipient_name",
                            "phone",
                            "region",
                            "city",
                            "address_line",
                            "postal_code",
                        ],
                    },
                    "remark": {
                        "type": "string",
                        "description": "备注信息",
                    },
                },
                "required": [
                    "merchant_url",
                    "merchant_did",
                    "merchant_public_key",
                    "cart_mandate_id",
                    "items",
                    "shipping_address",
                ],
            },
        ),
        Tool(
            name="ap2.sendPaymentMandate",
            description=(
                "构建并发送支付授权给商户服务器。"
                "此工具会使用之前创建的购物车授权，构建PaymentMandate，发送给商户完成支付流程。"
                "返回支付状态、支付收据和履约收据。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "merchant_url": {
                        "type": "string",
                        "description": "商户服务器URL",
                        "format": "uri",
                    },
                    "merchant_did": {
                        "type": "string",
                        "description": "商户DID",
                    },
                    "merchant_public_key": {
                        "type": "string",
                        "description": "商户公钥PEM（必需，用于验证merchant server返回的签名）",
                    },
                    "cart_mandate_id": {
                        "type": "string",
                        "description": "之前创建的购物车授权ID",
                    },
                    "payment_mandate_id": {
                        "type": "string",
                        "description": "支付授权ID（唯一标识）",
                    },
                    "refund_period": {
                        "type": "integer",
                        "description": "退款期限（天）",
                        "default": 30,
                    },
                },
                "required": [
                    "merchant_url",
                    "merchant_did",
                    "merchant_public_key",
                    "cart_mandate_id",
                    "payment_mandate_id",
                ],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> Sequence[TextContent]:
    """处理工具调用。"""
    global ap2_handler

    logger.info("Tool called", tool_name=name, args=arguments)

    try:
        if name == "ap2.createCartMandate":
            result = await ap2_handler.handle_create_cart_mandate(arguments)
        elif name == "ap2.sendPaymentMandate":
            result = await ap2_handler.handle_send_payment_mandate(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

        # 将结果转换为字符串格式返回
        return [
            TextContent(
                type="text", text=json.dumps(result, indent=2, ensure_ascii=False)
            )
        ]

    except Exception as e:
        logger.error("Tool execution failed", tool_name=name, error=str(e))
        error_result = {
            "ok": False,
            "error": {
                "code": "EXECUTION_ERROR",
                "message": str(e),
            },
        }
        return [
            TextContent(
                type="text",
                text=json.dumps(error_result, indent=2, ensure_ascii=False),
            )
        ]


def initialize_server() -> None:
    """初始化AP2服务器。"""
    global ap2_handler

    # 从环境变量读取DID凭证路径
    did_document_path = os.environ.get("ANP_DID_DOCUMENT_PATH")
    did_private_key_path = os.environ.get("ANP_DID_PRIVATE_KEY_PATH")

    # 如果环境变量未设置，使用默认的公共DID凭证
    if not did_document_path or not did_private_key_path:
        project_root = get_project_root()
        did_document_path = str(
            project_root / "docs" / "did_public" / "public-did-doc.json"
        )
        did_private_key_path = str(
            project_root / "docs" / "did_public" / "public-private-key.pem"
        )
        logger.info(
            "Using default DID credentials",
            did_doc=did_document_path,
            private_key=did_private_key_path,
        )
    else:
        logger.info(
            "Using DID credentials from environment variables",
            did_doc=did_document_path,
            private_key=did_private_key_path,
        )

    # 加载DID文档和密钥（仅用于shopper客户端）
    did_document = load_json(Path(did_document_path))
    client_did = did_document["id"]
    payment_private_key = load_text(Path(did_private_key_path))
    shopper_public_key = public_key_from_did_document(did_document)

    ap2_handler = AP2Handler(
        did_document_path=did_document_path,
        private_key_path=did_private_key_path,
        client_did=client_did,
        payment_private_key=payment_private_key,
        shopper_public_key=shopper_public_key,
    )

    logger.info("AP2 MCP server initialized", client_did=client_did)


async def run_server():
    """运行MCP服务器。"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


@click.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="设置日志级别",
)
@click.option(
    "--reload",
    is_flag=True,
    help="启用开发热重载",
)
def main(log_level: str, reload: bool) -> None:
    """运行 MCP2ANP AP2 支付流程服务器（stdio 模式）。

    环境变量:
        ANP_DID_DOCUMENT_PATH: DID 文档 JSON 文件路径
        ANP_DID_PRIVATE_KEY_PATH: DID 私钥 PEM 文件路径

    如果未设置环境变量，将使用默认的公共 DID 凭证。
    """
    setup_logging(log_level)

    # 初始化服务器
    initialize_server()

    if reload:
        logger.info("Starting MCP2ANP AP2 server with hot reload enabled")
    else:
        logger.info("Starting MCP2ANP AP2 server")

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error("Server error", error=str(e))
        raise


if __name__ == "__main__":
    main()

