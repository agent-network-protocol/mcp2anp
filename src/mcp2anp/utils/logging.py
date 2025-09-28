"""Logging configuration for the MCP2ANP server."""

import logging
import sys
from typing import Any

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False


def setup_logging(level: str = "INFO") -> None:
    """Set up structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    if STRUCTLOG_AVAILABLE:
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.CallsiteParameterAdder(
                    parameters=[structlog.processors.CallsiteParameter.FILENAME]
                ),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )


class LoggerMixin:
    """Mixin class to add structured logging to any class."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if STRUCTLOG_AVAILABLE:
            self.logger = structlog.get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

    def log_operation(
        self,
        operation: str,
        level: str = "info",
        **context: Any,
    ) -> None:
        """Log an operation with context.

        Args:
            operation: Description of the operation
            level: Log level (debug, info, warning, error)
            **context: Additional context to include in the log
        """
        if STRUCTLOG_AVAILABLE:
            log_func = getattr(self.logger, level)
            log_func(operation, **context)
        else:
            log_func = getattr(self.logger, level)
            message = f"{operation} - {context}" if context else operation
            log_func(message)
