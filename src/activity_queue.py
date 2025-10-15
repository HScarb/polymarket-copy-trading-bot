"""Activity queue abstract base class."""

from abc import ABC, abstractmethod
from typing import Callable, List


class ActivityQueue(ABC):
    """Message queue abstract base class for real-time wallet activity distribution."""

    @abstractmethod
    def enqueue(self, wallet_address: str, activities: List[dict]):
        """
        Enqueue activity list.

        Args:
            wallet_address: Wallet address
            activities: Activity data list
        """
        pass

    @abstractmethod
    def subscribe(self, wallet_address: str, callback: Callable[[List[dict]], None]):
        """
        Subscribe to specified wallet activities, register callback function.

        Args:
            wallet_address: Wallet address
            callback: Callback function that receives activity list as parameter
        """
        pass
