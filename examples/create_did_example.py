#!/usr/bin/env python3
"""
创建 DID 示例文件的辅助脚本

此脚本生成用于测试的 DID 文档和私钥文件
注意：这些是示例文件，不应在生产环境中使用
"""

import json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
import base58


def generate_ed25519_keypair():
    """生成 Ed25519 密钥对"""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return private_key, public_key


def public_key_to_multibase(public_key):
    """将公钥转换为 multibase 格式"""
    # Ed25519 公钥 (32 字节) + multicodec 前缀
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

    # Ed25519 multicodec 前缀: 0xed01
    multicodec_ed25519 = b'\xed\x01'
    multicodec_key = multicodec_ed25519 + public_key_bytes

    # Base58btc 编码 (multibase 前缀 'z')
    encoded = base58.b58encode(multicodec_key).decode('ascii')
    return f"z{encoded}"


def create_did_document(did_id: str, public_key_multibase: str) -> dict:
    """创建 DID 文档"""
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/suites/ed25519-2020/v1"
        ],
        "id": did_id,
        "verificationMethod": [
            {
                "id": f"{did_id}#key-1",
                "type": "Ed25519VerificationKey2020",
                "controller": did_id,
                "publicKeyMultibase": public_key_multibase
            }
        ],
        "authentication": [
            f"{did_id}#key-1"
        ],
        "assertionMethod": [
            f"{did_id}#key-1"
        ],
        "service": [
            {
                "id": f"{did_id}#agent-connect",
                "type": "AgentConnect",
                "serviceEndpoint": "https://example.com/agent-connect"
            }
        ],
        "created": "2024-09-28T10:00:00Z",
        "updated": "2024-09-28T10:00:00Z"
    }


def save_private_key_pem(private_key, file_path: Path):
    """保存私钥为 PEM 格式"""
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    with open(file_path, 'wb') as f:
        f.write(pem_private)


def main():
    """主函数"""
    print("🔑 生成 DID 示例文件...")

    # 创建输出目录
    examples_dir = Path(__file__).parent
    examples_dir.mkdir(exist_ok=True)

    # 生成密钥对
    print("   生成 Ed25519 密钥对...")
    private_key, public_key = generate_ed25519_keypair()

    # 转换公钥为 multibase 格式
    public_key_multibase = public_key_to_multibase(public_key)
    print(f"   公钥 (multibase): {public_key_multibase}")

    # 创建 DID
    did_id = "did:example:test123456789"
    print(f"   DID: {did_id}")

    # 创建 DID 文档
    did_document = create_did_document(did_id, public_key_multibase)

    # 保存 DID 文档
    did_doc_path = examples_dir / "did-example.json"
    with open(did_doc_path, 'w', encoding='utf-8') as f:
        json.dump(did_document, f, indent=2, ensure_ascii=False)
    print(f"   ✓ DID 文档已保存: {did_doc_path}")

    # 保存私钥
    private_key_path = examples_dir / "did-private-key.pem"
    save_private_key_pem(private_key, private_key_path)
    print(f"   ✓ 私钥已保存: {private_key_path}")

    print()
    print("📋 使用方法:")
    print(f"   DID 文档路径: {did_doc_path}")
    print(f"   私钥路径: {private_key_path}")
    print()
    print("⚠️  注意:")
    print("   - 这些是测试用的示例文件")
    print("   - 不要在生产环境中使用这些密钥")
    print("   - 私钥文件包含敏感信息，请妥善保管")

    return did_doc_path, private_key_path


if __name__ == "__main__":
    try:
        main()
        print("\n🎉 DID 示例文件创建完成!")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("💡 请运行: pip install cryptography base58")
    except Exception as e:
        print(f"❌ 创建失败: {e}")