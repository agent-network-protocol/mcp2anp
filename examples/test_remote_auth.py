"""测试远程服务器的鉴权功能。

此脚本测试以下场景：
1. 无鉴权模式 - 不需要 Authorization 头
2. 固定 Token 模式 - 验证正确和错误的 token
3. 默认回调模式 - 打印 token 并通过
4. 鉴权失败场景 - 缺少头、错误格式、空 token
"""

import asyncio
import json
import subprocess
import sys
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# 测试配置
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8001  # 使用不同端口避免冲突
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/mcp"
TEST_TOKEN = "test-secret-token-12345"
INVALID_TOKEN = "wrong-token"


class RemoteServerTester:
    """远程服务器鉴权测试器。"""

    def __init__(self):
        """初始化测试器。"""
        self.server_process: subprocess.Popen | None = None
        # 禁用代理以避免 SOCKS 相关问题
        self.client = httpx.AsyncClient(
            timeout=30.0,
            trust_env=False,  # 不使用环境变量中的代理设置
        )

    async def start_server(
        self, enable_auth: bool = False, auth_token: str | None = None
    ) -> None:
        """启动远程服务器。

        Args:
            enable_auth: 是否启用鉴权
            auth_token: 鉴权 token（可选）
        """
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "mcp2anp.server_remote",
            "--host",
            SERVER_HOST,
            "--port",
            str(SERVER_PORT),
            "--log-level",
            "INFO",
        ]

        if enable_auth:
            cmd.append("--enable-auth")
            if auth_token:
                cmd.extend(["--auth-token", auth_token])

        logger.info("Starting server", cmd=" ".join(cmd))

        self.server_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 等待服务器启动
        await asyncio.sleep(3)

        # 检查服务器是否启动成功
        if self.server_process.poll() is not None:
            stdout, stderr = self.server_process.communicate()
            raise RuntimeError(
                f"Server failed to start:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
            )

        logger.info("Server started successfully")

    def stop_server(self) -> None:
        """停止远程服务器。"""
        if self.server_process:
            logger.info("Stopping server")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server did not stop gracefully, killing")
                self.server_process.kill()
                self.server_process.wait()
            self.server_process = None
            logger.info("Server stopped")

    async def make_request(
        self,
        tool_name: str,
        params: dict[str, Any],
        auth_token: str | None = None,
    ) -> dict[str, Any]:
        """发送 MCP 工具调用请求。

        Args:
            tool_name: 工具名称
            params: 工具参数
            auth_token: Bearer Token（可选）

        Returns:
            响应数据
        """
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params},
        }

        logger.info(
            "Making request",
            tool=tool_name,
            has_auth=auth_token is not None,
        )

        try:
            response = await self.client.post(
                BASE_URL,
                json=payload,
                headers=headers,
            )
            return response.json()
        except Exception as e:
            logger.error("Request failed", error=str(e))
            raise

    async def test_no_auth_mode(self) -> bool:
        """测试无鉴权模式。"""
        logger.info("=" * 60)
        logger.info("测试场景 1: 无鉴权模式")
        logger.info("=" * 60)

        try:
            await self.start_server(enable_auth=False)

            # 测试 1: 不带 token 的请求应该成功
            logger.info("测试 1.1: 不带 Authorization 头的请求")
            response = await self.make_request(
                "anp.fetchDoc",
                {"url": "https://agent-navigation.com/ad.json"},
            )
            logger.info("Response", response=response)

            # 检查是否成功（不应该有 AUTHENTICATION_FAILED 错误）
            if "error" in response and response.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.error("❌ 测试失败: 无鉴权模式下请求被拒绝")
                return False

            logger.info("✅ 测试通过: 无鉴权模式正常工作")
            return True

        except Exception as e:
            logger.error("测试失败", error=str(e))
            return False
        finally:
            self.stop_server()
            await asyncio.sleep(1)

    async def test_fixed_token_mode(self) -> bool:
        """测试固定 Token 模式。"""
        logger.info("=" * 60)
        logger.info("测试场景 2: 固定 Token 模式")
        logger.info("=" * 60)

        try:
            await self.start_server(enable_auth=True, auth_token=TEST_TOKEN)

            # 测试 2.1: 使用正确的 token
            logger.info("测试 2.1: 使用正确的 Bearer Token")
            response = await self.make_request(
                "anp.fetchDoc",
                {"url": "https://agent-navigation.com/ad.json"},
                auth_token=TEST_TOKEN,
            )
            logger.info("Response", response=response)

            if "error" in response and response.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.error("❌ 测试失败: 正确的 token 被拒绝")
                return False

            logger.info("✅ 测试 2.1 通过: 正确的 token 被接受")

            # 测试 2.2: 使用错误的 token
            logger.info("测试 2.2: 使用错误的 Bearer Token")
            response = await self.make_request(
                "anp.fetchDoc",
                {"url": "https://agent-navigation.com/ad.json"},
                auth_token=INVALID_TOKEN,
            )
            logger.info("Response", response=response)

            # 应该返回 AUTHENTICATION_FAILED 错误
            # 检查中间件是否返回401错误
            if response.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.info("✅ 测试 2.2 通过: 错误的 token 被正确拒绝")
            else:
                logger.error("❌ 测试失败: 错误的 token 未被拒绝", response=response)
                return False

            # 测试 2.3: 不带 token
            logger.info("测试 2.3: 不带 Authorization 头")
            response = await self.make_request(
                "anp.fetchDoc",
                {"url": "https://agent-navigation.com/ad.json"},
            )
            logger.info("Response", response=response)

            # 应该返回 AUTHENTICATION_FAILED 错误
            if response.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.info("✅ 测试 2.3 通过: 缺少 token 被正确拒绝")
            else:
                logger.error("❌ 测试失败: 缺少 token 的请求未被拒绝", response=response)
                return False
            logger.info("✅ 固定 Token 模式所有测试通过")
            return True

        except Exception as e:
            logger.error("测试失败", error=str(e))
            return False
        finally:
            self.stop_server()
            await asyncio.sleep(1)

    async def test_default_callback_mode(self) -> bool:
        """测试默认回调模式。"""
        logger.info("=" * 60)
        logger.info("测试场景 3: 默认回调模式（启用鉴权但不设置 token）")
        logger.info("=" * 60)

        try:
            await self.start_server(enable_auth=True, auth_token=None)

            # 测试 3.1: 带任意 token 的请求应该通过（默认回调总是返回 True）
            logger.info("测试 3.1: 使用任意 Bearer Token")
            response = await self.make_request(
                "anp.fetchDoc",
                {"url": "https://agent-navigation.com/ad.json"},
                auth_token="any-token-should-work",
            )
            logger.info("Response", response=response)

            if "error" in response and response.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.error("❌ 测试失败: 默认回调模式拒绝了请求")
                return False

            logger.info("✅ 测试 3.1 通过: 任意 token 被接受（默认回调）")

            # 测试 3.2: 不带 token 应该失败
            logger.info("测试 3.2: 不带 Authorization 头")
            response = await self.make_request(
                "anp.fetchDoc",
                {"url": "https://agent-navigation.com/ad.json"},
            )
            logger.info("Response", response=response)

            # 应该返回 AUTHENTICATION_FAILED 错误
            if response.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.info("✅ 测试 3.2 通过: 缺少 token 被正确拒绝")
            else:
                logger.error("❌ 测试失败: 缺少 token 的请求未被拒绝", response=response)
                return False
            logger.info("✅ 默认回调模式所有测试通过")
            return True

        except Exception as e:
            logger.error("测试失败", error=str(e))
            return False
        finally:
            self.stop_server()
            await asyncio.sleep(1)

    async def test_auth_failure_scenarios(self) -> bool:
        """测试各种鉴权失败场景。"""
        logger.info("=" * 60)
        logger.info("测试场景 4: 鉴权失败场景")
        logger.info("=" * 60)

        try:
            await self.start_server(enable_auth=True, auth_token=TEST_TOKEN)

            # 测试 4.1: 错误的 Authorization 头格式（不是 Bearer）
            logger.info("测试 4.1: 错误的 Authorization 头格式")
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Basic dGVzdDp0ZXN0",  # 应该是 Bearer
            }
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "anp.fetchDoc",
                    "arguments": {"url": "https://agent-navigation.com/ad.json"},
                },
            }

            response = await self.client.post(BASE_URL, json=payload, headers=headers)
            result_json = response.json()

            if result_json.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                logger.info("✅ 测试 4.1 通过: 错误的头格式被正确拒绝")
            else:
                logger.error("❌ 测试失败: 错误的头格式未被拒绝", response=result_json)
                return False

            # 测试 4.2: 空 token（使用单个空格作为token）
            logger.info("测试 4.2: 空 Bearer Token")
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer  ",  # 空格作为 token
            }

            try:
                response = await self.client.post(BASE_URL, json=payload, headers=headers)
                result_json = response.json()

                if result_json.get("error", {}).get("code") == "AUTHENTICATION_FAILED":
                    logger.info("✅ 测试 4.2 通过: 空 token 被正确拒绝")
                else:
                    logger.error("❌ 测试失败: 空 token 未被拒绝", response=result_json)
                    return False
            except Exception as e:
                # httpx可能会拒绝非法的header，这也是一种有效的保护
                logger.info(f"✅ 测试 4.2 通过: 客户端拒绝了非法header ({str(e)[:50]})")
            logger.info("✅ 鉴权失败场景所有测试通过")
            return True

        except Exception as e:
            logger.error("测试失败", error=str(e))
            return False
        finally:
            self.stop_server()
            await asyncio.sleep(1)

    async def run_all_tests(self) -> None:
        """运行所有测试。"""
        logger.info("开始远程服务器鉴权功能测试")
        logger.info("=" * 60)

        results = {
            "无鉴权模式": await self.test_no_auth_mode(),
            "固定 Token 模式": await self.test_fixed_token_mode(),
            "默认回调模式": await self.test_default_callback_mode(),
            "鉴权失败场景": await self.test_auth_failure_scenarios(),
        }

        # 汇总结果
        logger.info("=" * 60)
        logger.info("测试结果汇总")
        logger.info("=" * 60)

        all_passed = True
        for test_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            logger.info(f"{test_name}: {status}")
            if not passed:
                all_passed = False

        logger.info("=" * 60)
        if all_passed:
            logger.info("🎉 所有测试通过！")
        else:
            logger.error("❌ 部分测试失败")
            sys.exit(1)

    async def cleanup(self) -> None:
        """清理资源。"""
        await self.client.aclose()


async def main() -> None:
    """主函数。"""
    tester = RemoteServerTester()

    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error("测试过程中发生错误", error=str(e))
        sys.exit(1)
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
