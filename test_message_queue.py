#!/usr/bin/env python3
"""
测试消息队列重构功能

这个脚本验证：
1. InMemoryActivityQueue 的基本功能
2. 订阅和发布机制
3. 多个订阅者的处理
"""

import time
from datetime import datetime
from typing import List

from src.in_memory_activity_queue import InMemoryActivityQueue
from src.logger import setup_logger

# 设置日志
log = setup_logger(level=20)  # INFO 级别


class ActivityCollector:
    """收集活动的辅助类，用于测试"""

    def __init__(self, name: str):
        self.name = name
        self.collected_activities = []

    def handle(self, activities: List[dict]):
        """处理活动的回调函数"""
        log.info(f"[{self.name}] 收到 {len(activities)} 条活动")
        self.collected_activities.extend(activities)


def test_basic_queue():
    """测试基本队列功能"""
    log.info("=" * 60)
    log.info("测试 1: 基本队列功能")
    log.info("=" * 60)

    # 创建队列
    queue = InMemoryActivityQueue(max_workers=2)

    # 创建订阅者
    collector1 = ActivityCollector("订阅者1")
    collector2 = ActivityCollector("订阅者2")

    # 订阅钱包
    wallet = "0x1234567890abcdef"
    queue.subscribe(wallet, collector1.handle)
    queue.subscribe(wallet, collector2.handle)

    # 模拟活动数据
    mock_activities = [
        {
            'transaction_hash': f'0xabc{i}',
            'market_id': f'market_{i}',
            'timestamp': datetime.now().isoformat()
        }
        for i in range(5)
    ]

    # 发布活动
    log.info(f"发布 {len(mock_activities)} 条活动到钱包 {wallet}")
    queue.enqueue(wallet, mock_activities)

    # 等待异步处理完成
    time.sleep(1)

    # 验证结果
    assert len(collector1.collected_activities) == 5, f"订阅者1应该收到5条活动，实际收到 {len(collector1.collected_activities)}"
    assert len(collector2.collected_activities) == 5, f"订阅者2应该收到5条活动，实际收到 {len(collector2.collected_activities)}"

    log.info("✓ 测试通过：两个订阅者都收到了所有活动")

    # 关闭队列
    queue.shutdown()
    log.info("队列已关闭\n")


def test_multiple_wallets():
    """测试多个钱包"""
    log.info("=" * 60)
    log.info("测试 2: 多钱包订阅")
    log.info("=" * 60)

    queue = InMemoryActivityQueue(max_workers=2)

    # 为不同钱包创建订阅者
    wallet1 = "0xwallet1"
    wallet2 = "0xwallet2"

    collector1 = ActivityCollector("钱包1订阅者")
    collector2 = ActivityCollector("钱包2订阅者")

    queue.subscribe(wallet1, collector1.handle)
    queue.subscribe(wallet2, collector2.handle)

    # 发布到钱包1
    activities1 = [{'tx': f'w1_tx_{i}'} for i in range(3)]
    queue.enqueue(wallet1, activities1)

    # 发布到钱包2
    activities2 = [{'tx': f'w2_tx_{i}'} for i in range(2)]
    queue.enqueue(wallet2, activities2)

    # 等待处理
    time.sleep(1)

    # 验证
    assert len(collector1.collected_activities) == 3, "钱包1订阅者应该收到3条活动"
    assert len(collector2.collected_activities) == 2, "钱包2订阅者应该收到2条活动"

    log.info("✓ 测试通过：每个订阅者只收到对应钱包的活动")

    queue.shutdown()
    log.info("队列已关闭\n")


def test_no_subscribers():
    """测试没有订阅者的情况"""
    log.info("=" * 60)
    log.info("测试 3: 无订阅者场景")
    log.info("=" * 60)

    queue = InMemoryActivityQueue(max_workers=2)

    # 发布到没有订阅者的钱包
    wallet = "0xnosubscribers"
    activities = [{'tx': 'test'}]

    log.info(f"发布活动到没有订阅者的钱包 {wallet}")
    queue.enqueue(wallet, activities)

    # 等待（虽然不应该有任何处理）
    time.sleep(0.5)

    log.info("✓ 测试通过：系统正常处理无订阅者情况（不会崩溃）")

    queue.shutdown()
    log.info("队列已关闭\n")


def test_callback_exception():
    """测试回调函数抛出异常的情况"""
    log.info("=" * 60)
    log.info("测试 4: 回调异常处理")
    log.info("=" * 60)

    queue = InMemoryActivityQueue(max_workers=2)

    # 创建一个会抛出异常的回调
    def failing_callback(activities: List[dict]):
        log.info("这个回调将抛出异常")
        raise ValueError("测试异常")

    # 创建一个正常的回调
    collector = ActivityCollector("正常订阅者")

    wallet = "0xtesterror"
    queue.subscribe(wallet, failing_callback)
    queue.subscribe(wallet, collector.handle)

    # 发布活动
    activities = [{'tx': 'test1'}, {'tx': 'test2'}]
    queue.enqueue(wallet, activities)

    # 等待处理
    time.sleep(1)

    # 验证正常订阅者仍然收到了活动
    assert len(collector.collected_activities) == 2, "正常订阅者应该收到活动"

    log.info("✓ 测试通过：异常回调不影响其他订阅者")

    queue.shutdown()
    log.info("队列已关闭\n")


def main():
    """运行所有测试"""
    log.info("开始测试消息队列功能...\n")

    try:
        test_basic_queue()
        test_multiple_wallets()
        test_no_subscribers()
        test_callback_exception()

        log.info("=" * 60)
        log.info("所有测试通过！✓")
        log.info("=" * 60)

    except AssertionError as e:
        log.error(f"测试失败: {e}")
        return 1
    except Exception as e:
        log.error(f"测试过程中发生错误: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
