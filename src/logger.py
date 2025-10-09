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
    """配置并返回全局日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 如果指定了日志目录,创建文件 handler
    if log_dir:
        # 获取项目根目录
        root_dir = Path(__file__).parent.parent
        log_path = root_dir / log_dir
        log_path.mkdir(parents=True, exist_ok=True)

        # 创建日志文件,按日期命名
        log_file = log_path / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# 创建全局 logger 实例(默认配置)
log = setup_logger()
