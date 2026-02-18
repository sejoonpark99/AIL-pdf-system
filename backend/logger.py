"""
Centralized logging configuration using Loguru.

This module provides:
- Structured logging with JSON formatting
- Terminal output only
- Contextual logging (session_id, company_name, etc.)
"""

import os
import sys
from loguru import logger

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

def setup_logger():
    """
    Configure Loguru with terminal output only.

    Logs are sent to stdout for terminal display.
    """

    # Remove default handler
    logger.remove()

    # Add stdout handler with readable formatting
    log_level = os.getenv("LOG_LEVEL", "DEBUG")
    logger.add(
        sys.stdout,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        level=log_level,
        serialize=False,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # Bind default context
    logger.configure(
        extra={
            "app": "pdf-analysis",
            "environment": ENVIRONMENT
        }
    )

    return logger


# Initialize logger on module import
log = setup_logger()


def get_logger():
    """
    Get the configured Loguru logger instance.

    Usage:
        from logger import get_logger
        log = get_logger()
        log.info("Something happened", user_id=123, action="login")
    """
    return log


def bind_context(**kwargs):
    """
    Bind context to logger for structured logging.

    Usage:
        logger_with_context = bind_context(
            session_id="abc123",
            request_id="xyz789"
        )
        logger_with_context.info("Processing request")

    The context will be included in all subsequent log messages.
    """
    return log.bind(**kwargs)
