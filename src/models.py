"""Database models for trade and checkpoint storage."""

from peewee import Model, CharField, DecimalField, DateTimeField
from playhouse.postgres_ext import PostgresqlExtDatabase

# Database instance will be initialized in DatabaseHandler
db = PostgresqlExtDatabase(None)


class Trade(Model):
    """Trade data model."""
    transaction_hash = CharField(primary_key=True, max_length=255)
    wallet_address = CharField(max_length=255, index=True)
    market_id = CharField(max_length=255, index=True)
    outcome = CharField(max_length=255)
    amount = DecimalField(max_digits=36, decimal_places=18)
    price = DecimalField(max_digits=36, decimal_places=18)
    timestamp = DateTimeField(index=True)

    class Meta:
        database = db
        table_name = 'trades'


class WalletCheckpoint(Model):
    """Wallet sync checkpoint model."""
    wallet_address = CharField(primary_key=True, max_length=255)
    last_synced_timestamp = DateTimeField(null=True, index=True)
    updated_at = DateTimeField(index=True)

    class Meta:
        database = db
        table_name = 'wallet_checkpoints'
