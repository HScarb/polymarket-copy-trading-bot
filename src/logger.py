"""Logging configuration and utilities."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = "polymarket_bot",
    level: int = logging.INFO,
    log_dir: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return global logger.

    Args:
        name: Logger name
        level: Logging level
        log_dir: Log directory path (optional)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # If log directory specified, create file handler
    if log_dir:
        # Get project root directory
        root_dir = Path(__file__).parent.parent
        log_path = root_dir / log_dir
        log_path.mkdir(parents=True, exist_ok=True)

        # Create log file, named by date
        log_file = log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Create global logger instance (default configuration)
log = setup_logger()
