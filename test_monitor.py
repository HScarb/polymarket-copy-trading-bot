"""测试完整的监控流程（模拟分页获取）"""
import time
from src.config_loader import load_config
from src.wallet_monitor import WalletMonitor
from src.logger import log

def test_monitor():
    """测试钱包监控"""
    config = load_config("config.yaml")

    db_url = config['database']['url']
    wallets = config['monitoring']['wallets']
    batch_size = 10  # 使用小批次测试分页逻辑

    log.info(f"开始测试监控，批次大小: {batch_size}")

    # 创建监控器
    monitor = WalletMonitor(
        wallets=wallets,
        poll_interval=300,  # 5分钟轮询一次（测试时只运行一轮）
        db_url=db_url,
        batch_size=batch_size,
        proxy=config.get('polymarket_api', {}).get('proxy'),
        timeout=30.0
    )

    # 启动监控
    monitor.start()

    # 等待10秒让第一轮完成
    log.info("等待第一轮监控完成...")
    time.sleep(10)

    # 停止监控
    monitor.stop()
    log.info("测试完成")

if __name__ == "__main__":
    test_monitor()
