from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from peewee import IntegrityError

from src.models import db, Trade, WalletCheckpoint


class DatabaseHandler:
    """数据库处理类"""

    @staticmethod
    def initialize_database(db_url: str):
        """连接数据库并创建表结构"""
        # 解析数据库 URL
        parsed = urlparse(db_url)

        # 初始化数据库连接
        db.init(
            parsed.path[1:],  # 去掉开头的 '/'
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432
        )

        # 连接数据库
        db.connect()

        # 创建表
        db.create_tables([Trade, WalletCheckpoint], safe=True)

    @staticmethod
    def save_trades(trades_data: list[dict]) -> int:
        """保存一批交易数据,返回新插入的记录数"""
        if not trades_data:
            return 0

        new_count = 0

        # 在事务中批量插入
        with db.atomic():
            for trade in trades_data:
                try:
                    Trade.create(**trade)
                    new_count += 1
                except IntegrityError:
                    # 主键冲突,说明交易已存在,跳过
                    continue

        return new_count

    @staticmethod
    def get_checkpoint(wallet_address: str) -> Optional[datetime]:
        """获取钱包的最后同步时间戳"""
        try:
            checkpoint = WalletCheckpoint.get(WalletCheckpoint.wallet_address == wallet_address)
            return checkpoint.last_synced_timestamp
        except WalletCheckpoint.DoesNotExist:
            return None

    @staticmethod
    def update_checkpoint(wallet_address: str, timestamp: datetime):
        """更新钱包的同步检查点"""
        now = datetime.now()

        # 使用 INSERT ... ON CONFLICT UPDATE
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
