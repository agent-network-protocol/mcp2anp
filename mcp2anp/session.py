"""会话管理模块。

提供会话配置、会话状态和会话管理器的实现。
"""

import asyncio
import time
import uuid

import structlog
from agent_connect.anp_crawler.anp_crawler import ANPCrawler

from .core.handlers import ANPHandler

logger = structlog.get_logger(__name__)


class SessionConfig:
    """会话配置信息。

    存储会话所需的 DID 凭证路径。
    """

    def __init__(self, did_document_path: str, private_key_path: str):
        """初始化会话配置。

        Args:
            did_document_path: DID 文档 JSON 文件路径
            private_key_path: DID 私钥 PEM 文件路径
        """
        self.did_document_path = did_document_path
        self.private_key_path = private_key_path


class SessionState:
    """会话状态，包含 ANPCrawler 和 ANPHandler。

    每个会话拥有独立的 ANPCrawler 和 ANPHandler 实例，
    以及独立的 DID 凭证配置。
    """

    def __init__(self, session_id: str, config: SessionConfig):
        """初始化会话状态。

        Args:
            session_id: 会话唯一标识符
            config: 会话配置
        """
        self.session_id = session_id
        self.config = config
        self.anp_crawler: ANPCrawler | None = None
        self.anp_handler: ANPHandler | None = None
        self._initialized = False
        self.created_at = time.time()
        self.last_accessed = time.time()

    def touch(self) -> None:
        """更新最后访问时间。"""
        self.last_accessed = time.time()

    def is_expired(self, timeout: int) -> bool:
        """检查会话是否已过期。

        Args:
            timeout: 超时时间（秒）

        Returns:
            bool: 是否已过期
        """
        return time.time() - self.last_accessed > timeout

    def initialize(self) -> None:
        """初始化会话的 ANPCrawler 和 ANPHandler。

        创建独立的 ANPCrawler 和 ANPHandler 实例。
        如果已初始化，则跳过。

        Raises:
            Exception: 初始化失败时抛出异常
        """
        if self._initialized:
            return

        try:
            logger.info(
                "Initializing session",
                session_id=self.session_id,
                did_doc=self.config.did_document_path,
                private_key=self.config.private_key_path,
            )

            # 创建 ANPCrawler 实例
            self.anp_crawler = ANPCrawler(
                did_document_path=self.config.did_document_path,
                private_key_path=self.config.private_key_path,
                cache_enabled=True
            )

            # 创建 ANPHandler 实例
            self.anp_handler = ANPHandler(self.anp_crawler)

            self._initialized = True
            logger.info("Session initialized successfully", session_id=self.session_id)

        except Exception as e:
            logger.error("Failed to initialize session", session_id=self.session_id, error=str(e))
            raise


class SessionManager:
    """管理所有会话状态。

    提供会话的创建、获取、删除和自动清理功能。
    """

    def __init__(self, timeout: int = 1800, cleanup_interval: int = 300):
        """初始化会话管理器。

        Args:
            timeout: 会话超时时间（秒），默认 30 分钟
            cleanup_interval: 清理任务执行间隔（秒），默认 5 分钟
        """
        self.sessions: dict[str, SessionState] = {}
        self.timeout = timeout
        self.cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task | None = None

    def create_session(self, config: SessionConfig) -> str:
        """创建新会话并返回会话 ID。

        Args:
            config: 会话配置

        Returns:
            str: 新创建的会话 ID

        Raises:
            Exception: 会话初始化失败时抛出异常
        """
        session_id = str(uuid.uuid4())
        session_state = SessionState(session_id, config)
        session_state.initialize()
        self.sessions[session_id] = session_state
        logger.info("Session created", session_id=session_id, total_sessions=len(self.sessions))
        return session_id

    def get_session(self, session_id: str) -> SessionState | None:
        """获取会话状态并更新访问时间。

        Args:
            session_id: 会话 ID

        Returns:
            SessionState | None: 会话状态，如果不存在则返回 None
        """
        session_state = self.sessions.get(session_id)
        if session_state:
            session_state.touch()
        return session_state

    def remove_session(self, session_id: str) -> None:
        """删除会话。

        Args:
            session_id: 要删除的会话 ID
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info("Session removed", session_id=session_id, total_sessions=len(self.sessions))

    async def cleanup_expired_sessions(self) -> None:
        """清理过期会话（后台任务）。

        定期检查并删除超时的会话。
        这是一个长期运行的后台任务。
        """
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                expired_sessions = [
                    session_id
                    for session_id, session_state in self.sessions.items()
                    if session_state.is_expired(self.timeout)
                ]

                if expired_sessions:
                    logger.info(
                        "Cleaning up expired sessions",
                        count=len(expired_sessions),
                        timeout=self.timeout
                    )
                    for session_id in expired_sessions:
                        self.remove_session(session_id)
                else:
                    logger.debug(
                        "No expired sessions to clean up",
                        total_sessions=len(self.sessions)
                    )

            except Exception as e:
                logger.error("Error in cleanup task", error=str(e))

    def start_cleanup_task(self) -> None:
        """启动清理任务。

        在后台启动定期清理过期会话的任务。
        """
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self.cleanup_expired_sessions())
            logger.info(
                "Cleanup task started",
                timeout=self.timeout,
                interval=self.cleanup_interval
            )

    def stop_cleanup_task(self) -> None:
        """停止清理任务。

        取消后台清理任务。
        """
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
            logger.info("Cleanup task stopped")
