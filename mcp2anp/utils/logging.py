"""Logging configuration for the MCP2ANP server."""

import logging
import sys
import os
from pathlib import Path
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
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Create file handler for log file
    log_file = logs_dir / "mcp2anp.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Create console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    # Configure root logger with both handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

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
