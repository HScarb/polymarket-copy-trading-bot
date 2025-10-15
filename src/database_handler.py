"""Database handler for trade persistence and checkpointing."""

from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from peewee import IntegrityError

from src.models import db, Trade, WalletCheckpoint


class DatabaseHandler:
    """Database handling class for trade and checkpoint operations."""

    @staticmethod
    def initialize_database(db_url: str):
        """
        Connect to database and create table structure.

        Args:
            db_url: PostgreSQL database URL
        """
        # Parse database URL
        parsed = urlparse(db_url)

        # Initialize database connection
        db.init(
            parsed.path[1:],  # Remove leading '/'
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432
        )

        # Connect to database
        db.connect()

        # Create tables
        db.create_tables([Trade, WalletCheckpoint], safe=True)

    @staticmethod
    def save_trades(trades_data: list[dict]) -> int:
        """
        Save batch of trade data, return count of newly inserted records.

        Args:
            trades_data: List of trade dictionaries

        Returns:
            Number of new records inserted
        """
        if not trades_data:
            return 0

        new_count = 0

        # Batch insert within transaction
        with db.atomic():
            for trade in trades_data:
                try:
                    Trade.create(**trade)
                    new_count += 1
                except IntegrityError:
                    # Primary key conflict, trade already exists, skip
                    continue

        return new_count

    @staticmethod
    def get_checkpoint(wallet_address: str) -> Optional[datetime]:
        """
        Get wallet's last sync timestamp.

        Args:
            wallet_address: Wallet address

        Returns:
            Last synced timestamp or None if not found
        """
        try:
            checkpoint = WalletCheckpoint.get(WalletCheckpoint.wallet_address == wallet_address)
            return checkpoint.last_synced_timestamp
        except WalletCheckpoint.DoesNotExist:
            return None

    @staticmethod
    def update_checkpoint(wallet_address: str, timestamp: datetime):
        """
        Update wallet's sync checkpoint.

        Args:
            wallet_address: Wallet address
            timestamp: Last synced timestamp
        """
        now = datetime.now()

        # Use INSERT ... ON CONFLICT UPDATE (UPSERT)
        WalletCheckpoint.insert(
            wallet_address=wallet_address,
            last_synced_timestamp=timestamp,
            updated_at=now
        ).on_conflict(
            conflict_target=[WalletCheckpoint.wallet_address],
            update={
                WalletCheckpoint.last_synced_timestamp: timestamp,
                WalletCheckpoint.updated_at: now
            }
        ).execute()
