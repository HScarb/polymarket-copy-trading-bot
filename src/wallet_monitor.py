import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from polymarket_apis.clients.data_client import PolymarketDataClient

from src.activity_queue import ActivityQueue
from src.logger import log

# 定义东八区时区（UTC+8）
TIMEZONE_UTC8 = timezone(timedelta(hours=8))


class WalletMonitor:
    """钱包监控器核心类"""

    def __init__(self, wallets: list[str], poll_interval: int, activity_queue: ActivityQueue, batch_size: int = 500, proxy: Optional[str] = None, timeout: float = 30.0):
        """
        初始化监控器,配置钱包、轮询间隔和消息队列

        Args:
            wallets: 要监控的钱包地址列表
            poll_interval: 轮询间隔（秒）
            activity_queue: 活动队列实例
            batch_size: 每次获取的最大活动数量
            proxy: 代理服务器地址（可选）
            timeout: API 超时时间（秒）
        """
        self.wallets = wallets
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.activity_queue = activity_queue
        self.data_client = PolymarketDataClient()

        # 配置 API 客户端
        if proxy:
            self.data_client.client = httpx.Client(proxy=proxy)
        else:
            self.data_client.client = httpx.Client()

        self.stop_event = threading.Event()
        self.executor: Optional[ThreadPoolExecutor] = None

        log.info(f"WalletMonitor 已初始化，监控 {len(wallets)} 个钱包")

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
        """
        监控单个钱包的私有方法

        使用当前时间（东八区）作为检查点（checkpoint），只获取此时间之后的新活动
        """
        log.info(f"开始监控钱包: {wallet_address}")

        # 设置检查点为当前时间（东八区）
        checkpoint = datetime.now(TIMEZONE_UTC8)
        log.info(f"钱包 {wallet_address}: 设置检查点为 {checkpoint}（东八区），监控此时间之后的活动")

        while not self.stop_event.is_set():
            try:
                total_activities = 0
                offset = 0

                # 分页获取数据
                while True:
                    # 设置查询结束时间为当前时间 + 1小时，防止间隔太小查不到数据
                    current_time = datetime.now(TIMEZONE_UTC8)
                    end_time = current_time + timedelta(hours=1)

                    # 构建请求参数 - 获取检查点之后的所有类型活动
                    params = {
                        "user": wallet_address,
                        "start": checkpoint,  # 查询起始时间（检查点）
                        "end": end_time,      # 查询结束时间（当前时间 + 1小时）
                        "limit": self.batch_size,
                        "offset": offset,
                        "sort_by": "TIMESTAMP",
                        "sort_direction": "ASC"  # 从旧到新排序，便于更新检查点
                    }
                    # 不指定 type 参数，获取所有类型的活动（TRADE, SPLIT, MERGE, REDEEM, REWARD, CONVERSION）

                    # 获取一批活动
                    activities = self.data_client.get_activity(**params)

                    # 如果没有数据，退出分页循环
                    if not activities:
                        log.debug(f"钱包 {wallet_address}: 已同步到最新")
                        break

                    # 将活动推送到消息队列
                    self.activity_queue.enqueue(wallet_address, activities)
                    total_activities += len(activities)

                    # 更新检查点为本批次最新的活动时间
                    latest_timestamp = self._get_latest_timestamp(activities)
                    if latest_timestamp:
                        checkpoint = latest_timestamp
                        log.debug(f"钱包 {wallet_address}: 更新检查点为 {checkpoint}")

                    # 如果返回数据少于 batch_size，说明已到达最新
                    if len(activities) < self.batch_size:
                        log.debug(f"钱包 {wallet_address}: 已追上最新活动（本批次 {len(activities)} < {self.batch_size}）")
                        break

                    # 更新 offset 用于下一次分页
                    offset += len(activities)

                if total_activities > 0:
                    log.info(f"钱包 {wallet_address}: 本轮共发现 {total_activities} 条新活动")
                else:
                    log.debug(f"钱包 {wallet_address}: 没有新活动")

            except Exception as e:
                log.error(f"监控钱包 {wallet_address} 时出错: {e}", exc_info=True)

            # 等待下一次轮询
            self.stop_event.wait(self.poll_interval)

    def _get_latest_timestamp(self, activities: list) -> Optional[datetime]:
        """
        从活动列表中获取最新的时间戳

        Args:
            activities: 活动对象列表

        Returns:
            最新的时间戳，如果无法解析则返回 None
        """
        if not activities:
            return None

        try:
            timestamps = []
            for activity in activities:
                ts = getattr(activity, 'timestamp', None)
                if ts:
                    parsed_ts = self._parse_timestamp(ts)
                    if parsed_ts:
                        timestamps.append(parsed_ts)

            return max(timestamps) if timestamps else None
        except Exception as e:
            log.warning(f"获取最新时间戳时出错: {e}")
            return None

    @staticmethod
    def _parse_timestamp(ts) -> Optional[datetime]:
        """
        解析时间戳为 datetime 对象

        Args:
            ts: 时间戳（可以是 datetime、字符串或数字）

        Returns:
            解析后的 datetime 对象，失败则返回 None
        """
        try:
            if isinstance(ts, datetime):
                return ts
            elif isinstance(ts, str):
                # 尝试解析 ISO 格式
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            elif isinstance(ts, (int, float)):
                # Unix 时间戳
                return datetime.fromtimestamp(ts)
        except Exception as e:
            log.warning(f"解析时间戳失败: {ts}, 错误: {e}")
        return None
