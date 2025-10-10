from abc import ABC, abstractmethod
from typing import Callable, List


class ActivityQueue(ABC):
    """消息队列抽象基类，用于实时分发钱包活动"""

    @abstractmethod
    def enqueue(self, wallet_address: str, activities: List[dict]):
        """
        将活动列表放入队列

        Args:
            wallet_address: 钱包地址
            activities: 活动数据列表
        """
        pass

    @abstractmethod
    def subscribe(self, wallet_address: str, callback: Callable[[List[dict]], None]):
        """
        订阅指定钱包的活动，注册回调函数

        Args:
            wallet_address: 钱包地址
            callback: 回调函数，接收活动列表作为参数
        """
        pass
