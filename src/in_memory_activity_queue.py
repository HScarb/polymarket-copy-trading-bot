from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List

from src.activity_queue import ActivityQueue
from src.logger import log


class InMemoryActivityQueue(ActivityQueue):
    """内存实现的活动队列，用于开发和测试"""

    def __init__(self, max_workers: int = 10):
        """
        初始化内存队列

        Args:
            max_workers: 回调执行的最大线程数
        """
        self.subscribers = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        log.info(f"InMemoryActivityQueue 已初始化，最大工作线程数: {max_workers}")

    def enqueue(self, wallet_address: str, activities: List[dict]):
        """
        将活动列表放入队列并通知所有订阅者

        Args:
            wallet_address: 钱包地址
            activities: 活动数据列表
        """
        if not activities:
            return

        # 检查是否有订阅者
        if wallet_address not in self.subscribers or not self.subscribers[wallet_address]:
            log.debug(f"钱包 {wallet_address} 没有订阅者，跳过通知")
            return

        log.info(f"钱包 {wallet_address}: 入队 {len(activities)} 条活动，通知 {len(self.subscribers[wallet_address])} 个订阅者")

        # 异步通知所有订阅者
        for callback in self.subscribers[wallet_address]:
            try:
                # 使用线程池执行回调，避免阻塞
                self.executor.submit(self._execute_callback, callback, activities, wallet_address)
            except Exception as e:
                log.error(f"提交回调任务失败: {e}")

    def subscribe(self, wallet_address: str, callback: Callable[[List[dict]], None]):
        """
        订阅指定钱包的活动，注册回调函数

        Args:
            wallet_address: 钱包地址
            callback: 回调函数，接收活动列表作为参数
        """
        self.subscribers[wallet_address].append(callback)
        log.info(f"新订阅者已添加至钱包: {wallet_address}，当前订阅者数量: {len(self.subscribers[wallet_address])}")

    def _execute_callback(self, callback: Callable, activities: List[dict], wallet_address: str):
        """
        执行回调函数，捕获并记录异常

        Args:
            callback: 回调函数
            activities: 活动数据列表
            wallet_address: 钱包地址
        """
        try:
            callback(activities)
        except Exception as e:
            log.error(f"执行钱包 {wallet_address} 的回调函数时出错: {e}", exc_info=True)

    def shutdown(self):
        """关闭线程池"""
        log.info("正在关闭 InMemoryActivityQueue 的线程池...")
        self.executor.shutdown(wait=True)
        log.info("InMemoryActivityQueue 已关闭")
