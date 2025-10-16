"""
Wallet monitoring module for Polymarket.

Monitors wallet addresses for new trading activities and
pushes them to an activity queue for processing.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Optional, List

import httpx
from polymarket_apis.clients.data_client import PolymarketDataClient

from src.activity_queue import ActivityQueue
from src.logger import log
from src.utils.time_utils import TIMEZONE_UTC8, get_latest_timestamp
from src.utils.activity_logger import log_activities


class WalletMonitor:
    """
    Core wallet monitoring class.

    Monitors specified wallet addresses for new activities and
    publishes them to an activity queue using a pub/sub pattern.
    """

    def __init__(
        self,
        wallets: List[str],
        poll_interval: int,
        activity_queue: ActivityQueue,
        batch_size: int = 500,
        proxy: Optional[str] = None,
        verify_ssl: bool = True
    ):
        """
        Initialize monitor with wallets and configuration.

        Args:
            wallets: List of wallet addresses to monitor
            poll_interval: Polling interval in seconds
            activity_queue: Activity queue instance for publishing events
            batch_size: Maximum activities to fetch per request
            proxy: Proxy server address (optional)
            timeout: API timeout in seconds
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        self.wallets = wallets
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.activity_queue = activity_queue
        self.data_client = PolymarketDataClient()

        # Configure API client
        self.data_client.client = httpx.Client(proxy=proxy, verify=verify_ssl) if proxy else httpx.Client(verify=verify_ssl)

        self.stop_event = threading.Event()
        self.executor: Optional[ThreadPoolExecutor] = None

        log.info(f"WalletMonitor initialized, monitoring {len(wallets)} wallet(s)")

    def start(self):
        """Start all monitoring tasks and thread pool."""
        log.info(f"Starting monitoring for {len(self.wallets)} wallet address(es)")

        # Create thread pool
        self.executor = ThreadPoolExecutor(max_workers=len(self.wallets))

        # Submit monitoring task for each wallet
        for wallet in self.wallets:
            self.executor.submit(self._monitor_wallet, wallet)

        log.info("All monitoring tasks started")

    def stop(self):
        """Gracefully stop all monitoring tasks."""
        log.info("Stopping monitoring...")
        self.stop_event.set()

        if self.executor:
            self.executor.shutdown(wait=True)

        log.info("Monitoring stopped")

    def _monitor_wallet(self, wallet_address: str):
        """
        Monitor a single wallet (runs in dedicated thread).

        Uses current time (UTC+8) as checkpoint and only fetches
        activities that occur after this time.

        Args:
            wallet_address: Wallet address to monitor
        """
        log.info(f"Started monitoring wallet: {wallet_address}")

        # Set checkpoint to current time (UTC+8)
        checkpoint = datetime.now(TIMEZONE_UTC8)
        log.info(
            f"Wallet {wallet_address}: Set checkpoint to {checkpoint} (UTC+8), "
            f"monitoring activities after this time"
        )

        while not self.stop_event.is_set():
            try:
                total_activities, updated_checkpoint = self._fetch_and_publish_activities(
                    wallet_address,
                    checkpoint
                )

                # Update checkpoint to latest activity timestamp
                if updated_checkpoint:
                    checkpoint = updated_checkpoint

                if total_activities > 0:
                    log.info(
                        f"Wallet {wallet_address}: Found {total_activities} new "
                        f"activity(ies) this round"
                    )
                else:
                    log.debug(f"Wallet {wallet_address}: No new activities")

            except Exception as e:
                log.error(f"Error monitoring wallet {wallet_address}: {e}", exc_info=True)

            # Wait for next poll
            self.stop_event.wait(self.poll_interval)

    def _fetch_and_publish_activities(
        self,
        wallet_address: str,
        checkpoint: datetime
    ) -> tuple[int, Optional[datetime]]:
        """
        Fetch activities from API and publish to queue.

        Args:
            wallet_address: Wallet address to fetch activities for
            checkpoint: Start time for fetching activities

        Returns:
            Tuple of (total_activities_count, updated_checkpoint)
            - total_activities_count: Total number of activities fetched
            - updated_checkpoint: Latest activity timestamp (or None if no activities)
        """
        total_activities = 0
        offset = 0
        latest_checkpoint = None

        # Paginated fetch
        while True:
            # Set end time to current time + 1 hour to prevent missing data
            current_time = datetime.now(TIMEZONE_UTC8)
            end_time = current_time + timedelta(hours=1)

            # Build request parameters - fetch all activity types after checkpoint
            params = {
                "user": wallet_address,
                "start": checkpoint,  # Query start time (checkpoint)
                "end": end_time,      # Query end time (current time + 1 hour)
                "limit": self.batch_size,
                "offset": offset,
                "sort_by": "TIMESTAMP",
                "sort_direction": "ASC"  # Sort old to new for checkpoint updates
            }
            # Don't specify 'type' parameter to fetch all activity types
            # (TRADE, SPLIT, MERGE, REDEEM, REWARD, CONVERSION)

            # Fetch a batch of activities
            activities = self.data_client.get_activity(**params)

            # If no data, exit pagination loop
            if not activities:
                log.debug(f"Wallet {wallet_address}: Synced to latest")
                break

            # Log activity summary
            log_activities(wallet_address, activities)

            # Push activities to message queue
            self.activity_queue.enqueue(wallet_address, activities)
            total_activities += len(activities)

            # Update checkpoint to the latest activity timestamp in this batch
            latest_timestamp = get_latest_timestamp(activities)
            if latest_timestamp:
                latest_checkpoint = latest_timestamp
                log.debug(f"Wallet {wallet_address}: Updated checkpoint to {latest_checkpoint}")

            # If returned data < batch_size, we've reached the latest
            if len(activities) < self.batch_size:
                log.debug(
                    f"Wallet {wallet_address}: Caught up to latest activities "
                    f"(this batch {len(activities)} < {self.batch_size})"
                )
                break

            # Update offset for next page
            offset += len(activities)

        return total_activities, latest_checkpoint
