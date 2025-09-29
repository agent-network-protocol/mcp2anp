#!/usr/bin/env python3
"""
单独测试每个 MCP2ANP 工具的功能

这个脚本单独测试每个工具，便于调试和理解每个工具的具体行为
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp2anp.server import call_tool


async def call_tool_safe(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """安全地调用工具并处理结果"""
    try:
        print(f"\n🔧 调用工具: {tool_name}")
        print(f"📥 参数: {json.dumps(arguments, indent=2, ensure_ascii=False)}")

        result = await call_tool(tool_name, arguments)

        # 从 TextContent 中提取 JSON
        if result and len(result) > 0:
            text_content = result[0].text
            parsed_result = json.loads(text_content)

            print(f"📤 结果: {json.dumps(parsed_result, indent=2, ensure_ascii=False)[:500]}...")
            return parsed_result
        else:
            print("❌ 没有返回结果")
            return {"ok": False, "error": {"code": "NO_RESULT", "message": "No result returned"}}

    except Exception as e:
        print(f"❌ 调用失败: {e}")
        return {"ok": False, "error": {"code": "CALL_ERROR", "message": str(e)}}


async def test_fetch_doc():
    """测试 fetchDoc 工具"""
    print("=" * 60)
    print("🌐 测试 anp.fetchDoc 工具")
    print("=" * 60)

    # 测试 1: 抓取主 Agent Description
    print("\n📋 测试 1: 抓取 Agent Description")
    url = "https://agent-connect.ai/agents/travel/mcp/agents/amap/ad.json"
    result = await call_tool_safe("anp.fetchDoc", {"url": url})

    if result.get("ok"):
        print("✅ 主文档抓取成功")

        # 分析返回的数据
        json_data = result.get("json", {})
        if json_data:
            print(f"   📊 Agent 信息:")
            print(f"     - ID: {json_data.get('id', 'N/A')}")
            print(f"     - 协议类型: {json_data.get('protocolType', 'N/A')}")
            print(f"     - 版本: {json_data.get('version', 'N/A')}")
            print(f"     - 名称: {json_data.get('name', 'N/A')}")

        # 分析链接
        links = result.get("links", [])
        print(f"   🔗 发现 {len(links)} 个链接:")
        for i, link in enumerate(links, 1):
            print(f"     {i}. {link.get('rel', 'unknown')}: {link.get('url', 'N/A')}")
            if link.get('protocol'):
                print(f"        协议: {link.get('protocol')}")

        return result
    else:
        print("❌ 主文档抓取失败")
        return result


async def test_fetch_interface(main_result: Dict[str, Any]):
    """测试抓取接口文档"""
    print("\n📋 测试 2: 抓取接口文档")

    if not main_result.get("ok"):
        print("❌ 跳过：主文档抓取失败")
        return {"ok": False}

    # 查找接口链接
    links = main_result.get("links", [])
    interface_links = [
        link for link in links
        if link.get("rel") in ["interface", "interfaces"] or
           "interface" in link.get("url", "").lower()
    ]

    if not interface_links:
        print("❌ 未找到接口链接")
        return {"ok": False}

    # 测试第一个接口链接
    interface_link = interface_links[0]
    interface_url = interface_link["url"]

    result = await call_tool_safe("anp.fetchDoc", {"url": interface_url})

    if result.get("ok"):
        print("✅ 接口文档抓取成功")

        json_data = result.get("json", {})
        if json_data:
            # OpenRPC 特定分析
            if "openrpc" in json_data:
                print(f"   📋 OpenRPC 版本: {json_data.get('openrpc', 'N/A')}")
                info = json_data.get("info", {})
                print(f"   📖 服务信息:")
                print(f"     - 标题: {info.get('title', 'N/A')}")
                print(f"     - 版本: {info.get('version', 'N/A')}")
                print(f"     - 描述: {info.get('description', 'N/A')[:100]}...")

                methods = json_data.get("methods", [])
                print(f"   🛠️  可用方法 ({len(methods)} 个):")
                for method in methods[:5]:  # 只显示前5个
                    print(f"     - {method.get('name', 'unknown')}: {method.get('summary', method.get('description', ''))[:60]}...")

        return result
    else:
        print("❌ 接口文档抓取失败")
        return result


async def test_invoke_openrpc(interface_result: Dict[str, Any]):
    """测试 OpenRPC 调用"""
    print("\n📋 测试 3: OpenRPC 方法调用")

    if not interface_result.get("ok"):
        print("❌ 跳过：接口文档获取失败")
        return {"ok": False}

    json_data = interface_result.get("json", {})
    methods = json_data.get("methods", [])

    if not methods:
        print("❌ 未找到可调用的方法")
        return {"ok": False}

    # 分析方法，寻找简单的查询方法
    print(f"   🔍 分析 {len(methods)} 个可用方法...")

    simple_methods = []
    for method in methods:
        method_name = method.get("name", "")
        params = method.get("params", [])

        # 寻找参数较少的方法
        if len(params) <= 2:
            simple_methods.append(method)
            print(f"     🟢 简单方法: {method_name} (参数: {len(params)})")
        else:
            print(f"     🟡 复杂方法: {method_name} (参数: {len(params)})")

    # 选择测试方法
    if simple_methods:
        test_method = simple_methods[0]
    else:
        test_method = methods[0]

    method_name = test_method.get("name")
    method_params = test_method.get("params", [])

    print(f"\n   🎯 选择测试方法: {method_name}")

    # 构造测试参数
    test_params = {}
    for param in method_params:
        param_name = param.get("name", "")
        param_schema = param.get("schema", {})
        param_type = param_schema.get("type", "string")

        # 根据参数类型构造默认值
        if param_type == "string":
            test_params[param_name] = "test"
        elif param_type == "number" or param_type == "integer":
            test_params[param_name] = 1
        elif param_type == "boolean":
            test_params[param_name] = True
        elif param_type == "array":
            test_params[param_name] = []
        elif param_type == "object":
            test_params[param_name] = {}

    # 推测端点 URL
    server_url = json_data.get("servers", [{}])[0].get("url", "")
    if not server_url:
        # 如果没有服务器 URL，从原始 URL 推测
        server_url = "https://agent-connect.ai/agents/travel/mcp/agents/amap/rpc"

    print(f"   🌐 端点 URL: {server_url}")
    print(f"   📋 测试参数: {json.dumps(test_params, ensure_ascii=False)}")

    # 执行调用
    result = await call_tool_safe("anp.invokeOpenRPC", {
        "endpoint": server_url,
        "method": method_name,
        "params": test_params,
        "id": "test-call-123"
    })

    if result.get("ok"):
        print("✅ OpenRPC 调用成功")
        rpc_result = result.get("result", {})
        print(f"   📤 返回结果: {json.dumps(rpc_result, indent=2, ensure_ascii=False)[:200]}...")
    else:
        print("⚠️  OpenRPC 调用失败（这可能是正常的）")
        error = result.get("error", {})
        print(f"   ❌ 错误信息: {error.get('message', 'Unknown error')}")
        print("   💡 可能的原因:")
        print("     - 需要有效的认证凭据")
        print("     - 参数格式不正确")
        print("     - 服务端点不可用")

    return result


async def test_set_auth():
    """测试 setAuth 工具"""
    print("=" * 60)
    print("🔐 测试 anp.setAuth 工具")
    print("=" * 60)

    # 检查示例文件是否存在
    examples_dir = Path(__file__).parent
    did_doc_path = examples_dir / "did-example.json"
    did_key_path = examples_dir / "did-private-key.pem"

    print(f"   📄 DID 文档路径: {did_doc_path}")
    print(f"   🔑 私钥路径: {did_key_path}")

    if not did_doc_path.exists():
        print(f"❌ DID 文档不存在: {did_doc_path}")
        print("💡 请运行: python examples/create_did_example.py")
        return {"ok": False}

    if not did_key_path.exists():
        print(f"❌ 私钥文件不存在: {did_key_path}")
        print("💡 请运行: python examples/create_did_example.py")
        return {"ok": False}

    # 显示 DID 文档内容
    try:
        with open(did_doc_path, 'r', encoding='utf-8') as f:
            did_doc = json.load(f)
        print(f"   📋 DID: {did_doc.get('id', 'N/A')}")
        verification_methods = did_doc.get('verificationMethod', [])
        if verification_methods:
            print(f"   🔐 验证方法: {verification_methods[0].get('type', 'N/A')}")
    except Exception as e:
        print(f"❌ 读取 DID 文档失败: {e}")
        return {"ok": False}

    # 调用 setAuth
    result = await call_tool_safe("anp.setAuth", {
        "did_document_path": str(did_doc_path),
        "did_private_key_path": str(did_key_path)
    })

    if result.get("ok"):
        print("✅ DID 认证设置成功")
        print("   🎯 后续的 fetchDoc 和 invokeOpenRPC 调用将使用此认证")
    else:
        print("❌ DID 认证设置失败")
        error = result.get("error", {})
        print(f"   💥 错误: {error.get('message', 'Unknown error')}")

    return result


async def main():
    """主函数 - 依次测试所有工具"""
    print("🧪 MCP2ANP 工具单独测试")
    print("🎯 目标 URL: https://agent-connect.ai/agents/travel/mcp/agents/amap/ad.json")
    print()

    # 1. 测试 setAuth（可选，但建议先测试）
    auth_result = await test_set_auth()

    # 2. 测试 fetchDoc - 主文档
    main_result = await test_fetch_doc()

    # 3. 测试 fetchDoc - 接口文档
    interface_result = await test_fetch_interface(main_result)

    # 4. 测试 invokeOpenRPC
    invoke_result = await test_invoke_openrpc(interface_result)

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)

    results = [
        ("DID 认证设置", auth_result.get("ok", False)),
        ("文档抓取", main_result.get("ok", False)),
        ("接口抓取", interface_result.get("ok", False)),
        ("OpenRPC 调用", invoke_result.get("ok", False)),
    ]

    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")

    success_count = sum(1 for _, success in results if success)
    print(f"\n📈 成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")

    if success_count >= 2:
        print("🎉 基本功能正常！")
    else:
        print("⚠️  需要检查配置和网络连接")


if __name__ == "__main__":
    asyncio.run(main())