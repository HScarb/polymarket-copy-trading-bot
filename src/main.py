import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import List

from src.config_loader import load_config
from src.logger import setup_logger
from src.wallet_monitor import WalletMonitor
from src.in_memory_activity_queue import InMemoryActivityQueue
from src.copy_trader import CopyTrader

# 定义东八区时区（UTC+8）
TIMEZONE_UTC8 = timezone(timedelta(hours=8))


def create_activity_queue(config: dict):
    """
    根据配置创建活动队列实例

    Args:
        config: 配置字典

    Returns:
        ActivityQueue 实例
    """
    queue_config = config.get('queue', {})
    queue_type = queue_config.get('type', 'memory')

    if queue_type == 'memory':
        memory_config = queue_config.get('memory', {})
        max_workers = memory_config.get('max_workers', 10)
        return InMemoryActivityQueue(max_workers=max_workers)
    elif queue_type == 'rabbitmq':
        # TODO: 实现 RabbitMQ 队列
        raise NotImplementedError("RabbitMQ 队列尚未实现")
    else:
        raise ValueError(f"不支持的队列类型: {queue_type}")


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
        monitoring_config = config['monitoring']
        wallets = monitoring_config['wallets']
        poll_interval = monitoring_config['poll_interval_seconds']
        batch_size = monitoring_config.get('batch_size', 500)
        api_config = config.get('polymarket_api', {})
        proxy = api_config.get('proxy')
        timeout = api_config.get('timeout', 30.0)
        
        # 提取 Polygon RPC 配置
        polygon_rpc_config = config.get('polygon_rpc', {})

        # 创建活动队列
        activity_queue = create_activity_queue(config)
        log.info(f"活动队列已创建: {type(activity_queue).__name__}")

        # 初始化复制交易器（如果配置了用户钱包）
        copy_traders = []
        user_wallets = config.get('user_wallets', [])

        if user_wallets:
            log.info(f"检测到 {len(user_wallets)} 个用户钱包配置，正在初始化复制交易器...")

            for wallet_config in user_wallets:
                try:
                    trader = CopyTrader(
                        wallet_config=wallet_config,
                        activity_queue=activity_queue,
                        polygon_rpc_config=polygon_rpc_config
                    )
                    copy_traders.append(trader)

                    # 为每个目标钱包启动复制交易
                    for target_wallet in wallets:
                        trader.run(target_wallet)

                    log.info(f"复制交易器 '{wallet_config['name']}' 已启动")

                except Exception as e:
                    log.error(
                        f"初始化复制交易器 '{wallet_config.get('name', 'unknown')}' 失败: {e}",
                        exc_info=True
                    )
        else:
            log.info("未配置用户钱包，仅运行监控模式（活动将在 WalletMonitor 中打印）")

        # 创建监控器
        monitor = WalletMonitor(
            wallets=wallets,
            poll_interval=poll_interval,
            activity_queue=activity_queue,
            batch_size=batch_size,
            proxy=proxy,
            timeout=timeout
        )

        # 设置信号处理,支持优雅退出
        def signal_handler(sig, frame):
            log.info("收到退出信号,正在关闭...")

            # 打印复制交易统计
            for trader in copy_traders:
                trader.print_stats()

            monitor.stop()
            if hasattr(activity_queue, 'shutdown'):
                activity_queue.shutdown()
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
        log.error(f"程序启动失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
