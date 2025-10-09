from urllib.parse import urlparse

from peewee import IntegrityError

from src.models import db, Trade


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
        db.create_tables([Trade], safe=True)

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
