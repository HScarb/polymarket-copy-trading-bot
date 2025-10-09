import logging
import signal
import sys

from src.config_loader import load_config
from src.logger import setup_logger
from src.wallet_monitor import WalletMonitor


def main():
    """程序入口"""
    try:
        # 加载配置
        config = load_config("config.yaml")

        # 配置日志
        log_config = config.get('logging', {})
        log_dir = log_config.get('log_dir', 'logs')
        log_level_str = log_config.get('level', 'INFO')
        log_level = getattr(logging, log_level_str, logging.INFO)

        # 重新初始化日志
        log = setup_logger(log_dir=log_dir, level=log_level)
        log.info("正在加载配置文件...")

        # 提取配置
        db_url = config['database']['url']
        monitoring_config = config['monitoring']
        wallets = monitoring_config['wallets']
        poll_interval = monitoring_config['poll_interval_seconds']
        batch_size = monitoring_config.get('batch_size', 500)
        api_config = config.get('polymarket_api', {})
        proxy = api_config.get('proxy')
        timeout = api_config.get('timeout', 30.0)

        # 创建监控器
        monitor = WalletMonitor(
            wallets=wallets,
            poll_interval=poll_interval,
            db_url=db_url,
            batch_size=batch_size,
            proxy=proxy,
            timeout=timeout
        )

        # 设置信号处理,支持优雅退出
        def signal_handler(sig, frame):
            log.info("收到退出信号,正在关闭...")
            monitor.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 启动监控
        monitor.start()

        # 保持主线程运行
        log.info("监控运行中,按 Ctrl+C 退出...")
        while True:
            signal.pause() if hasattr(signal, 'pause') else monitor.stop_event.wait(3600)

    except FileNotFoundError as e:
        log.error(f"配置文件错误: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"程序启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
