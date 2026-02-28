#!/usr/bin/env python3
"""
MCP AP2 客户端 Demo

这个脚本演示如何使用 MCP 官方 SDK 创建客户端来调用 mcp2anp AP2 服务器。
它演示完整的 AP2 支付流程：创建购物车授权和发送支付授权。
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import structlog
from anp.authentication.verification_methods import EcdsaSecp256k1VerificationKey2019
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = structlog.get_logger(__name__)


def get_local_ip() -> str:
    """获取本地IP地址。"""
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(load_text(path))


def public_key_from_did_document(did_document: dict) -> str:
    """从 DID 文档中获取 secp256k1 公钥 PEM。"""
    method = did_document["verificationMethod"][0]
    verifier = EcdsaSecp256k1VerificationKey2019.from_dict(method)
    return verifier.public_key.public_bytes(
        Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")


async def demo_ap2_flow():
    """演示AP2支付流程"""
    print("=== MCP AP2 客户端演示 ===")
    print("注意: DID 认证通过环境变量配置，或使用默认凭证\n")

    # 配置 MCP 服务器参数
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "mcp2anp.ap2_server"],
        env=None,
    )

    # 获取商户服务器URL和DID
    project_root = Path(__file__).parent.parent
    did_document_path = project_root / "docs" / "did_public" / "public-did-doc.json"
    if not did_document_path.exists():
        raise FileNotFoundError(
            f"未找到 DID 文档: {did_document_path}. "
            "请确认已同步 docs/did_public/ 目录。"
        )

    did_document = load_json(did_document_path)
    merchant_did = did_document["id"]
    merchant_public_key = public_key_from_did_document(did_document)

    local_ip = get_local_ip()
    merchant_url = f"http://{local_ip}:8889"

    print(f"[Client] Merchant URL: {merchant_url}")
    print(f"[Client] Merchant DID: {merchant_did}")
    print("[Client] Merchant public key: 已从 DID 文档加载\n")

    # 使用 MCP SDK 的 stdio_client 连接服务器
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化会话
            await session.initialize()

            # 获取工具列表
            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"可用工具数量: {len(tools)}")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description or '无描述'}")

            # 步骤1: 创建购物车授权
            print("\n" + "=" * 60)
            print("步骤 1: 创建购物车授权 (ap2.createCartMandate)")
            print("=" * 60)

            cart_mandate_id = "cart-20250127-001"
            items = [
                {
                    "id": "sku-001",
                    "quantity": 1,
                    "price": 299.99,
                    "currency": "CNY",
                    "label": "Product SKU-001",
                    "options": {
                        "color": "Space Gray",
                        "memory": "16GB",
                        "storage": "512GB",
                    },
                    "remark": "Please ship ASAP",
                }
            ]
            shipping_address = {
                "recipient_name": "Zhang San",
                "phone": "13800138000",
                "region": "Beijing",
                "city": "Beijing",
                "address_line": "123 Some Street, Chaoyang District",
                "postal_code": "100000",
            }

            try:
                cart_result = await session.call_tool(
                    "ap2.createCartMandate",
                    arguments={
                        "merchant_url": merchant_url,
                        "merchant_did": merchant_did,
                        "merchant_public_key": merchant_public_key,
                        "cart_mandate_id": cart_mandate_id,
                        "items": items,
                        "shipping_address": shipping_address,
                        "remark": "Please ship ASAP",
                    },
                )

                print("\n购物车授权创建结果:")
                for content in cart_result.content:
                    content_dict = content.model_dump()
                    if content_dict.get("type") == "text":
                        try:
                            text_data = json.loads(content_dict.get("text", "{}"))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                            if text_data.get("ok"):
                                print(f"\n✓ 购物车授权创建成功")
                                print(f"  - Cart Mandate ID: {text_data.get('cart_mandate_id')}")
                                print(f"  - Cart Hash: {text_data.get('cart_hash', '')[:32]}...")
                        except json.JSONDecodeError:
                            print(content_dict.get("text"))
            except Exception as e:
                print(f"❌ 创建购物车授权失败: {e}")
                print(f"提示: 请确保商户服务器正在运行 ({merchant_url})")
                return

            # 步骤2: 发送支付授权
            print("\n" + "=" * 60)
            print("步骤 2: 发送支付授权 (ap2.sendPaymentMandate)")
            print("=" * 60)

            payment_mandate_id = "pm_20250127_001"

            try:
                payment_result = await session.call_tool(
                    "ap2.sendPaymentMandate",
                    arguments={
                        "merchant_url": merchant_url,
                        "merchant_did": merchant_did,
                        "merchant_public_key": merchant_public_key,
                        "cart_mandate_id": cart_mandate_id,
                        "payment_mandate_id": payment_mandate_id,
                        "refund_period": 30,
                    },
                )

                print("\n支付授权发送结果:")
                for content in payment_result.content:
                    content_dict = content.model_dump()
                    if content_dict.get("type") == "text":
                        try:
                            text_data = json.loads(content_dict.get("text", "{}"))
                            print(json.dumps(text_data, indent=2, ensure_ascii=False))
                            if text_data.get("ok"):
                                print(f"\n✓ 支付授权发送成功")
                                print(f"  - Payment Mandate ID: {text_data.get('payment_mandate_id')}")
                                print(f"  - Status: {text_data.get('status')}")
                                print(f"  - Payment ID: {text_data.get('payment_id')}")
                                if text_data.get("payment_receipt"):
                                    print(f"  - Payment Receipt: 已收到")
                                if text_data.get("fulfillment_receipt"):
                                    print(f"  - Fulfillment Receipt: 已收到")
                        except json.JSONDecodeError:
                            print(content_dict.get("text"))
            except Exception as e:
                print(f"❌ 发送支付授权失败: {e}")
                print(f"提示: 请确保商户服务器正在运行 ({merchant_url})")
                return

            print("\n" + "=" * 60)
            print("✓ AP2 支付流程完成")
            print("=" * 60)


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    print("MCP2ANP AP2 客户端演示 (使用官方 MCP SDK)")
    print("=" * 60)
    print("\n使用说明:")
    print("1. 首先启动商户服务器: python examples/merchant_server.py")
    print("2. 然后运行此脚本: python examples/mcp_ap2_client_demo.py")
    print("3. 此脚本会自动连接到 mcp2anp.ap2_server 并完成支付流程\n")

    try:
        # AP2支付流程演示
        await demo_ap2_flow()

        print("\n=== 演示完成 ===")
        print("演示内容包括:")
        print("- ap2.createCartMandate: 创建购物车授权请求")
        print("- ap2.sendPaymentMandate: 发送支付授权完成支付流程")
        print("\n环境变量配置:")
        print("- ANP_DID_DOCUMENT_PATH: 自定义 DID 文档路径")
        print("- ANP_DID_PRIVATE_KEY_PATH: 自定义 DID 私钥路径")
        print("（未设置时使用默认凭证）")

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        logger.error("主程序执行失败", error=str(e))
        print(f"程序执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

