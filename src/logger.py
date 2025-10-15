"""Logging configuration and utilities."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


def setup_logger(
    name: str = "polymarket_bot",
    level: int = logging.INFO,
    log_dir: Optional[str] = None,
    log_filename: Optional[str] = None
) -> logging.Logger:
    """
    Configure and return global logger with daily rotation support.

    Args:
        name: Logger name
        level: Logging level
        log_dir: Log directory path (relative to project root, optional)
        log_filename: Base log filename without extension (optional, defaults to date format YYYY-MM-DD)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Clear existing handlers to allow reconfiguration
    if logger.handlers:
        logger.handlers.clear()

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

    # If log directory specified, create file handler with daily rotation
    if log_dir:
        # Get project root directory (parent of src/)
        root_dir = Path(__file__).parent.parent
        log_path = root_dir / log_dir
        log_path.mkdir(parents=True, exist_ok=True)

        # Determine log filename
        if log_filename:
            # Use custom filename with .log extension
            log_file = log_path / f"{log_filename}.log"
        else:
            # Use date-based filename (default behavior)
            log_file = log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log"

        # Create TimedRotatingFileHandler for daily rotation
        # - when='midnight': rotate at midnight
        # - interval=1: rotate every 1 day
        # - backupCount=30: keep 30 days of logs
        # - encoding='utf-8': UTF-8 encoding
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)

        # Set log file name suffix for rotated files
        file_handler.suffix = "%Y-%m-%d"

        logger.addHandler(file_handler)

        # Log the file location for debugging
        logger.info(f"Logging to file: {log_file.absolute()}")

    return logger


# Create global logger instance (default configuration)
log = setup_logger()
