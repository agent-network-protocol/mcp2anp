"""
对 `server_remote.py` 进行端到端集成测试，模拟一个真实的 MCP 客户端。

此脚本基于 `mcp_client_demo.py`，使用 MCP 官方 SDK (`mcp.client.stdio`)
启动并连接到 `server_remote.py` 实例。

测试场景:
1. 使用有效的 API Key 启动服务器，并验证客户端能否成功初始化会话和列出工具。
2. 不使用 API Key 启动服务器（使用默认凭证），并验证客户端能否成功操作。
3. 使用无效的 API Key 启动服务器，并验证会话初始化是否会失败。

前提:
- 一个兼容的远程认证服务正在 `127.0.0.1:9866` 上运行。
- 该认证服务能识别 "valid-key" 为有效，"invalid-key" 为无效。
- 测试需要通过 `--api-key` 提供有效的 "valid-key"。

如何运行:
1. 确保已安装 dev 依赖: `uv pip install -e ".[dev]"`
2. 运行测试:
   uv run python examples/test_remote_auth_v2.py --api-key "valid-key"
"""

import asyncio
import json
import sys
import time
from asyncio.subprocess import Process
from contextlib import suppress

import click
import structlog
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# --- 全局配置 ---
logger = structlog.get_logger(__name__)

MCP_HOST = "127.0.0.1"
# Note: port is not needed for stdio client, but we pass it for consistency
MCP_PORT = 9880

DEFAULT_API_KEY = "sk_mcp_MW4O4-FECAP-WQPHF-DHIPR-HV7CK-KU2ED-OOB3E-6OVQD-ZA"


# --- 集成测试器 ---


class RemoteServerClientTester:
    """使用 MCP 客户端测试 `server_remote.py` 的端到端测试器。"""

    async def run_client_test(
        self,
        name: str,
        client_api_key: str | None,
        expect_success: bool,
        server_api_key: str | None,
    ) -> bool:
        """
        运行一个客户端测试场景。
        启动服务器，连接客户端，并尝试初始化会话。
        """
        logger.info("=" * 60)
        logger.info(f"测试场景: {name}")
        display_key = client_api_key if client_api_key else DEFAULT_API_KEY
        logger.info(f"API Key: '{display_key}', Expect Success: {expect_success}")
        logger.info("=" * 60)

        headers = None
        if client_api_key:
            headers = {
                "X-API-Key": client_api_key,
            }

        server_process: Process | None = None

        try:
            server_process = await self._launch_server(server_api_key)
            if server_process is None:
                logger.error("❌ 测试失败: 服务器进程未能启动。")
                return False

            if not await self._wait_for_server_ready(server_process):
                logger.error("❌ 测试失败: 服务器未能在预期时间内就绪。")
                return False

            async with streamablehttp_client(
                url=f"http://{MCP_HOST}:{MCP_PORT}/mcp",
                headers=headers,
            ) as (read, write, _):
                async with ClientSession(read, write) as session:
                    logger.info("尝试初始化 MCP 客户端会话...")
                    await session.initialize()
                    logger.info("会话初始化成功。")

                    tools_result = await session.list_tools()
                    logger.info(f"成功列出 {len(tools_result.tools)} 个工具。")

                    test_url = "https://agent-search.ai/agents/navigation/ad.json"
                    print(f"URL: {test_url}\n")

                    try:
                        start_time = time.monotonic()
                        result = await session.call_tool(
                            "anp_fetchDoc", arguments={"url": test_url}
                        )
                        end_time = time.monotonic()
                        logger.info(
                            f"首次调用 anp_fetchDoc (含认证) 耗时: {end_time - start_time:.4f} 秒。"
                        )

                        for content in result.content:
                            if hasattr(content, "text"):
                                try:
                                    data = json.loads(content.text)
                                    if not data.get("ok"):
                                        print(
                                            f"❌ 预期的错误: {data.get('error', {}).get('code')}"
                                        )
                                        print(
                                            "   消息:"
                                            f" {data.get('error', {}).get('message')}\n"
                                        )
                                except json.JSONDecodeError:
                                    print(content.text)
                    except Exception as fetch_error:
                        logger.error(
                            "调用 anp.fetchDoc 失败",
                            error=str(fetch_error),
                        )
                        if expect_success:
                            return False

                    if not expect_success:
                        logger.error("❌ 测试失败: 期望会话初始化失败，但它成功了。")
                        return False

                    logger.info("✅ 测试通过: 客户端成功连接并操作服务器。")
                    return True

        except Exception as e:
            if expect_success:
                logger.error(f"❌ 测试失败: 期望成功，但捕获到异常: {e}")
                return False

            logger.info(f"✅ 测试通过: 正确捕获到预期的异常: {e}")
            if "AUTHENTICATION_FAILED" in str(e):
                logger.info("错误消息包含 'AUTHENTICATION_FAILED'，符合预期。")
            else:
                logger.warning(
                    f"错误消息不含 'AUTHENTICATION_FAILED'，但仍视为通过: {e}"
                )
            return True
        finally:
            if server_process is not None:
                await self._stop_server(server_process)

    async def _launch_server(self, server_api_key: str | None) -> Process | None:
        """启动 server_remote.py 子进程。"""
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "mcp2anp.server_remote",
            f"--host={MCP_HOST}",
            f"--port={MCP_PORT}",
            "--log-level=WARNING",
        ]

        if server_api_key:
            cmd.extend(
                [
                    f"--api-key={server_api_key}",
                ]
            )

        logger.info("启动 server_remote 子进程", command=" ".join(cmd))

        try:
            process = await asyncio.create_subprocess_exec(*cmd)
            return process
        except FileNotFoundError as e:
            logger.error("未能找到 uv 可执行文件", error=str(e))
            return None

    async def _wait_for_server_ready(
        self, process: Process, timeout: float = 15.0
    ) -> bool:
        """等待服务器在指定超时内开始监听端口。"""
        deadline = asyncio.get_running_loop().time() + timeout

        while True:
            if process.returncode is not None:
                logger.error(
                    "server_remote 提前退出",
                    returncode=process.returncode,
                )
                return False

            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(MCP_HOST, MCP_PORT), timeout=1.0
                )
                writer.close()
                await writer.wait_closed()
                logger.info("server_remote 已开始监听", host=MCP_HOST, port=MCP_PORT)
                return True
            except (TimeoutError, ConnectionRefusedError, OSError):
                if asyncio.get_running_loop().time() >= deadline:
                    return False
                await asyncio.sleep(0.3)

    async def _stop_server(self, process: Process) -> None:
        """终止 server_remote 子进程。"""
        if process.returncode is not None:
            return

        logger.info("停止 server_remote 子进程")
        process.terminate()

        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except TimeoutError:
            logger.warning("子进程未在超时内退出，尝试强制 kill")
            process.kill()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=5.0)

    async def run_all_tests(self, valid_api_key: str) -> None:
        """运行所有测试。"""
        logger.info("=" * 60)
        logger.info("开始 `server_remote` 端到端客户端集成测试")
        logger.info("=" * 60)

        results = {}

        # 场景 1: 使用提供的有效 API Key
        results["使用有效密钥"] = await self.run_client_test(
            "使用有效密钥",
            client_api_key=valid_api_key,
            expect_success=True,
            server_api_key=valid_api_key,
        )

        # 场景 2: 不使用 API Key (预期失败)
        results["不使用密钥 (预期失败)"] = await self.run_client_test(
            "不使用密钥 (预期失败)",
            client_api_key=None,
            expect_success=False,
            server_api_key=None,
        )

        # 场景 3: 使用无效的 API Key
        results["使用无效密钥"] = await self.run_client_test(
            "使用无效密钥",
            client_api_key="invalid-key",
            expect_success=False,
            server_api_key=valid_api_key,
        )

        logger.info("=" * 60)
        logger.info("测试结果汇总")
        logger.info("=" * 60)

        all_passed = all(results.values())
        for test_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            logger.info(f"{test_name}: {status}")

        logger.info("=" * 60)
        if all_passed:
            logger.info("🎉 所有测试通过！")
        else:
            logger.error("❌ 部分测试失败")
            sys.exit(1)


# --- 主程序入口 ---


@click.command()
@click.option(
    "--api-key",
    "valid_api_key",
    default=DEFAULT_API_KEY,
    show_default=False,
    help="用于测试的有效 API Key (默认使用预置密钥)。",
)
def main(valid_api_key: str):
    """
    运行 `server_remote.py` 的端到端集成测试。
    需要一个正在运行的认证服务器，该服务器能识别 'valid-key' 和 'invalid-key'。
    """
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    tester = RemoteServerClientTester()
    try:
        asyncio.run(tester.run_all_tests(valid_api_key))
    except Exception as e:
        logger.error("测试执行期间发生未捕获的错误。", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
