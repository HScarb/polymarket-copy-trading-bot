"""In-memory activity queue implementation."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List

from src.activity_queue import ActivityQueue
from src.logger import log


class InMemoryActivityQueue(ActivityQueue):
    """In-memory activity queue implementation for development and testing."""

    def __init__(self, max_workers: int = 10):
        """
        Initialize in-memory queue.

        Args:
            max_workers: Maximum number of worker threads for callback execution
        """
        self.subscribers = defaultdict(list)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        log.info(f"InMemoryActivityQueue initialized with max workers: {max_workers}")

    def enqueue(self, wallet_address: str, activities: List[dict]):
        """
        Enqueue activity list and notify all subscribers.

        Args:
            wallet_address: Wallet address
            activities: Activity data list
        """
        if not activities:
            return

        # Check if there are subscribers
        if wallet_address not in self.subscribers or not self.subscribers[wallet_address]:
            log.debug(f"Wallet {wallet_address} has no subscribers, skipping notification")
            return

        log.info(
            f"Wallet {wallet_address}: Enqueued {len(activities)} activity(ies), "
            f"notifying {len(self.subscribers[wallet_address])} subscriber(s)"
        )

        # Asynchronously notify all subscribers
        for callback in self.subscribers[wallet_address]:
            try:
                # Use thread pool to execute callback, avoid blocking
                self.executor.submit(self._execute_callback, callback, activities, wallet_address)
            except Exception as e:
                log.error(f"Failed to submit callback task: {e}")

    def subscribe(self, wallet_address: str, callback: Callable[[List[dict]], None]):
        """
        Subscribe to specified wallet activities, register callback function.

        Args:
            wallet_address: Wallet address
            callback: Callback function that receives activity list as parameter
        """
        self.subscribers[wallet_address].append(callback)
        log.info(
            f"New subscriber added to wallet: {wallet_address}, "
            f"current subscriber count: {len(self.subscribers[wallet_address])}"
        )

    def _execute_callback(self, callback: Callable, activities: List[dict], wallet_address: str):
        """
        Execute callback function, capture and log exceptions.

        Args:
            callback: Callback function
            activities: Activity data list
            wallet_address: Wallet address
        """
        try:
            callback(activities)
        except Exception as e:
            log.error(f"Error executing callback for wallet {wallet_address}: {e}", exc_info=True)

    def shutdown(self):
        """Shutdown thread pool."""
        log.info("Shutting down InMemoryActivityQueue thread pool...")
        self.executor.shutdown(wait=True)
        log.info("InMemoryActivityQueue shut down")
