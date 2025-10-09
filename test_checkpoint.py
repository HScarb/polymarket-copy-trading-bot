"""测试分页和断点续传功能"""
from datetime import datetime

from src.config_loader import load_config
from src.database_handler import DatabaseHandler
from src.logger import log

def test_checkpoint():
    """测试检查点功能"""
    # 加载配置
    config = load_config("config.yaml")
    db_url = config['database']['url']

    # 初始化数据库
    DatabaseHandler.initialize_database(db_url)
    log.info("数据库已初始化")

    # 测试钱包地址
    test_wallet = "0x55be7aa03ecfbe37aa5460db791205f7ac9ddca3"

    # 1. 测试获取不存在的检查点
    checkpoint = DatabaseHandler.get_checkpoint(test_wallet)
    log.info(f"初始检查点: {checkpoint}")
    assert checkpoint is None, "初始检查点应为 None"

    # 2. 测试创建检查点
    test_time = datetime(2024, 1, 1, 12, 0, 0)
    DatabaseHandler.update_checkpoint(test_wallet, test_time)
    log.info(f"创建检查点: {test_time}")

    # 3. 测试读取检查点
    checkpoint = DatabaseHandler.get_checkpoint(test_wallet)
    log.info(f"读取检查点: {checkpoint}")
    assert checkpoint is not None, "检查点应存在"
    assert checkpoint == test_time, f"检查点时间应为 {test_time}"

    # 4. 测试更新检查点
    new_time = datetime(2024, 1, 2, 12, 0, 0)
    DatabaseHandler.update_checkpoint(test_wallet, new_time)
    log.info(f"更新检查点: {new_time}")

    checkpoint = DatabaseHandler.get_checkpoint(test_wallet)
    log.info(f"再次读取检查点: {checkpoint}")
    assert checkpoint == new_time, f"检查点时间应为 {new_time}"

    log.info("✅ 所有检查点测试通过！")

if __name__ == "__main__":
    test_checkpoint()
