import logging
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import List

from src.config_loader import load_config
from src.logger import setup_logger
from src.wallet_monitor import WalletMonitor
from src.in_memory_activity_queue import InMemoryActivityQueue

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


def example_activity_handler(activities: List[dict]):
    """
    示例回调函数：处理接收到的活动

    Args:
        activities: 活动数据列表
    """
    from src.logger import log
    log.info(f"[示例处理器] 收到 {len(activities)} 条新活动")

    for activity in activities:
        # 提取基本信息
        activity_type = getattr(activity, 'type', 'N/A')
        tx_hash = getattr(activity, 'transaction_hash', 'N/A')
        market_id = getattr(activity, 'condition_id', 'N/A')
        market_title = getattr(activity, 'title', 'N/A')  # 市场名称
        outcome = getattr(activity, 'outcome', 'N/A')
        side = getattr(activity, 'side', 'N/A')  # BUY 或 SELL

        # 提取数量和价格信息
        size = getattr(activity, 'size', 0)  # 代币数量
        price = getattr(activity, 'price', 0)  # 单价
        cash_amount = getattr(activity, 'cash_amount', 0)  # 现金总额

        # 如果 cash_amount 为 0，用 size × price 计算
        if cash_amount == 0 and size and price:
            cash_amount = float(size) * float(price)

        # 提取其他信息
        maker_address = getattr(activity, 'maker_address', 'N/A')
        timestamp_raw = getattr(activity, 'timestamp', None)

        # 将时间戳转换为东八区时间
        if timestamp_raw:
            try:
                if isinstance(timestamp_raw, datetime):
                    # 如果已经是 datetime 对象，转换为东八区
                    timestamp = timestamp_raw.astimezone(TIMEZONE_UTC8)
                elif isinstance(timestamp_raw, str):
                    # 如果是字符串，解析后转换为东八区
                    dt = datetime.fromisoformat(timestamp_raw.replace('Z', '+00:00'))
                    timestamp = dt.astimezone(TIMEZONE_UTC8)
                elif isinstance(timestamp_raw, (int, float)):
                    # 如果是 Unix 时间戳，转换为东八区
                    dt = datetime.fromtimestamp(timestamp_raw, tz=timezone.utc)
                    timestamp = dt.astimezone(TIMEZONE_UTC8)
                else:
                    timestamp = 'N/A'
            except Exception as e:
                log.warning(f"解析时间戳失败: {timestamp_raw}, 错误: {e}")
                timestamp = timestamp_raw
        else:
            timestamp = 'N/A'

        # 打印详细信息
        log.info(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        log.info(f"  类型: {activity_type} | 方向: {side}")
        log.info(f"  交易哈希: {tx_hash}")
        log.info(f"  市场: {market_title}")
        log.info(f"  市场ID: {market_id}")
        log.info(f"  结果: {outcome}")
        log.info(f"  代币数量: {size} | 单价: {price} | 总金额: ${cash_amount}")
        log.info(f"  Maker: {maker_address}")
        log.info(f"  时间: {timestamp}")


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

        # 创建活动队列
        activity_queue = create_activity_queue(config)
        log.info(f"活动队列已创建: {type(activity_queue).__name__}")

        # 订阅钱包活动（示例）
        for wallet in wallets:
            activity_queue.subscribe(wallet, example_activity_handler)
            log.info(f"已为钱包 {wallet} 注册示例处理器")

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
