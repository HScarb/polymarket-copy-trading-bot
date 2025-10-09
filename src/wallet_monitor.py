import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import httpx
from polymarket_apis.clients.data_client import PolymarketDataClient

from src.database_handler import DatabaseHandler
from src.logger import log


class WalletMonitor:
    """钱包监控器核心类"""

    def __init__(self, wallets: list[str], poll_interval: int, db_url: str, proxy: Optional[str] = None, timeout: float = 30.0):
        """初始化监控器,配置钱包、轮询间隔和数据库"""
        self.wallets = wallets
        self.poll_interval = poll_interval
        self.data_client = PolymarketDataClient()

        # 配置 API 客户端
        if proxy:
            self.data_client.client = httpx.Client(proxy=proxy)
        else:
            self.data_client.client = httpx.Client()

        self.stop_event = threading.Event()
        self.executor: Optional[ThreadPoolExecutor] = None

        # 初始化数据库
        DatabaseHandler.initialize_database(db_url)
        log.info(f"数据库已初始化: {db_url}")

    def start(self):
        """启动所有监控任务和线程池"""
        log.info(f"开始监控 {len(self.wallets)} 个钱包地址")

        # 创建线程池
        self.executor = ThreadPoolExecutor(max_workers=len(self.wallets))

        # 为每个钱包提交监控任务
        for wallet in self.wallets:
            self.executor.submit(self._monitor_wallet, wallet)

        log.info("所有监控任务已启动")

    def stop(self):
        """平滑地停止所有监控任务"""
        log.info("正在停止监控...")
        self.stop_event.set()

        if self.executor:
            self.executor.shutdown(wait=True)

        log.info("监控已停止")

    def _monitor_wallet(self, wallet_address: str):
        """监控单个钱包的私有方法"""
        log.info(f"开始监控钱包: {wallet_address}")

        while not self.stop_event.is_set():
            try:
                # 获取钱包交易活动
                activities = self.data_client.get_activity(
                    user=wallet_address,
                    type="TRADE"
                )

                # 转换为数据库格式
                trades_data = self._convert_activities_to_trades(activities, wallet_address)

                # 保存到数据库
                new_count = DatabaseHandler.save_trades(trades_data)

                if new_count > 0:
                    log.info(f"钱包 {wallet_address}: 发现并保存了 {new_count} 条新交易")
                else:
                    log.debug(f"钱包 {wallet_address}: 没有新交易")

            except Exception as e:
                log.error(f"监控钱包 {wallet_address} 时出错: {e}")

            # 等待下一次轮询
            self.stop_event.wait(self.poll_interval)

    def _convert_activities_to_trades(self, activities: list, wallet_address: str) -> list[dict]:
        """将 Activity 对象列表转换为适合存入数据库的字典列表"""
        trades_data = []

        for activity in activities:
            try:
                # 根据 polymarket_apis 的 Activity 结构提取字段
                trade = {
                    'transaction_hash': getattr(activity, 'transaction_hash', None),
                    'wallet_address': wallet_address,
                    'market_id': getattr(activity, 'condition_id', None),
                    'outcome': getattr(activity, 'outcome', None),
                    'amount': str(getattr(activity, 'size', 0)),
                    'price': str(getattr(activity, 'price', 0)),
                    'timestamp': self._parse_timestamp(getattr(activity, 'timestamp', None))
                }

                # 确保所有必需字段都存在
                if trade['transaction_hash'] and trade['market_id']:
                    trades_data.append(trade)

            except Exception as e:
                log.warning(f"转换活动数据时出错: {e}, 活动数据: {activity}")
                continue

        return trades_data

    @staticmethod
    def _parse_timestamp(ts) -> datetime:
        """解析时间戳为 datetime 对象"""
        if isinstance(ts, datetime):
            return ts
        elif isinstance(ts, str):
            # 尝试解析 ISO 格式
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        elif isinstance(ts, (int, float)):
            # Unix 时间戳
            return datetime.fromtimestamp(ts)
        else:
            return datetime.now()
