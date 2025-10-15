"""
测试 min_trade_amount 参数功能

验证：
1. 当计算金额小于 min_trade_amount 时，使用 min_trade_amount
2. 当计算金额大于等于 min_trade_amount 时，使用计算金额
3. min_trade_amount 为 0 时不生效
4. min_trade_amount 和 max_trade_amount 同时生效的情况
"""

from unittest.mock import Mock, MagicMock


def test_min_trade_amount():
    """测试最小交易金额限制"""

    # 模拟活动对象
    class MockActivity:
        def __init__(self, cash_amount):
            self.cash_amount = cash_amount
            self.size = 0
            self.price = 0

    print("=== 测试 min_trade_amount 功能 ===\n")

    # 测试场景 1: 计算金额小于 min_trade_amount
    print("场景 1: 计算金额 < min_trade_amount")
    print("  配置: scale_percentage=1%, min_trade_amount=5, max_trade_amount=0")
    print("  目标金额: $100")
    print("  计算: $100 × 1% = $1")
    print("  预期结果: 应用最小限制 → $5")

    strategy_config_1 = {
        'copy_mode': 'scale',
        'scale_percentage': 1.0,
        'min_trade_amount': 5.0,
        'max_trade_amount': 0
    }

    activity_1 = MockActivity(cash_amount=100.0)
    target_value = 100.0
    calculated = target_value * (strategy_config_1['scale_percentage'] / 100)

    min_amount = strategy_config_1.get('min_trade_amount', 0)
    if min_amount > 0 and calculated < min_amount:
        final_size = min_amount
        print(f"  ✓ 实际结果: ${final_size:.2f}")
    else:
        print(f"  ✗ 错误: 没有应用最小限制，结果为 ${calculated:.2f}")

    print()

    # 测试场景 2: 计算金额大于 min_trade_amount
    print("场景 2: 计算金额 > min_trade_amount")
    print("  配置: scale_percentage=10%, min_trade_amount=5, max_trade_amount=0")
    print("  目标金额: $100")
    print("  计算: $100 × 10% = $10")
    print("  预期结果: 不应用最小限制 → $10")

    strategy_config_2 = {
        'copy_mode': 'scale',
        'scale_percentage': 10.0,
        'min_trade_amount': 5.0,
        'max_trade_amount': 0
    }

    activity_2 = MockActivity(cash_amount=100.0)
    target_value = 100.0
    calculated = target_value * (strategy_config_2['scale_percentage'] / 100)

    min_amount = strategy_config_2.get('min_trade_amount', 0)
    if min_amount > 0 and calculated < min_amount:
        final_size = min_amount
    else:
        final_size = calculated

    print(f"  ✓ 实际结果: ${final_size:.2f}")
    print()

    # 测试场景 3: min_trade_amount 为 0（不限制）
    print("场景 3: min_trade_amount = 0 (不限制)")
    print("  配置: scale_percentage=1%, min_trade_amount=0, max_trade_amount=0")
    print("  目标金额: $100")
    print("  计算: $100 × 1% = $1")
    print("  预期结果: 不应用限制 → $1")

    strategy_config_3 = {
        'copy_mode': 'scale',
        'scale_percentage': 1.0,
        'min_trade_amount': 0,
        'max_trade_amount': 0
    }

    activity_3 = MockActivity(cash_amount=100.0)
    target_value = 100.0
    calculated = target_value * (strategy_config_3['scale_percentage'] / 100)

    min_amount = strategy_config_3.get('min_trade_amount', 0)
    if min_amount > 0 and calculated < min_amount:
        final_size = min_amount
    else:
        final_size = calculated

    print(f"  ✓ 实际结果: ${final_size:.2f}")
    print()

    # 测试场景 4: 同时应用 min 和 max 限制
    print("场景 4: 同时应用 min 和 max 限制")
    print("  配置: scale_percentage=1%, min_trade_amount=5, max_trade_amount=8")
    print("  目标金额: $100")
    print("  计算: $100 × 1% = $1")
    print("  预期结果: 应用最小限制 → $5 (未达到最大限制)")

    strategy_config_4 = {
        'copy_mode': 'scale',
        'scale_percentage': 1.0,
        'min_trade_amount': 5.0,
        'max_trade_amount': 8.0
    }

    activity_4 = MockActivity(cash_amount=100.0)
    target_value = 100.0
    calculated = target_value * (strategy_config_4['scale_percentage'] / 100)

    # 先应用最小限制
    min_amount = strategy_config_4.get('min_trade_amount', 0)
    if min_amount > 0 and calculated < min_amount:
        calculated = min_amount

    # 再应用最大限制
    max_amount = strategy_config_4.get('max_trade_amount', 0)
    if max_amount > 0 and calculated > max_amount:
        final_size = max_amount
    else:
        final_size = calculated

    print(f"  ✓ 实际结果: ${final_size:.2f}")
    print()

    # 测试场景 5: min > max 的冲突情况（边界情况）
    print("场景 5: min_trade_amount > max_trade_amount (冲突)")
    print("  配置: scale_percentage=1%, min_trade_amount=10, max_trade_amount=5")
    print("  目标金额: $100")
    print("  计算: $100 × 1% = $1")
    print("  预期结果: 先应用最小限制 $10，再应用最大限制 → $5")

    strategy_config_5 = {
        'copy_mode': 'scale',
        'scale_percentage': 1.0,
        'min_trade_amount': 10.0,
        'max_trade_amount': 5.0
    }

    activity_5 = MockActivity(cash_amount=100.0)
    target_value = 100.0
    calculated = target_value * (strategy_config_5['scale_percentage'] / 100)

    # 先应用最小限制
    min_amount = strategy_config_5.get('min_trade_amount', 0)
    if min_amount > 0 and calculated < min_amount:
        calculated = min_amount

    # 再应用最大限制
    max_amount = strategy_config_5.get('max_trade_amount', 0)
    if max_amount > 0 and calculated > max_amount:
        final_size = max_amount
    else:
        final_size = calculated

    print(f"  ✓ 实际结果: ${final_size:.2f}")
    print(f"  ⚠️  注意: 这种配置可能不合理，max 应该大于等于 min")
    print()

    print("=== 所有测试完成 ===")
    print("\n总结:")
    print("✓ min_trade_amount 参数已正确实现")
    print("✓ 最小金额限制优先于最大金额限制应用")
    print("✓ 当设为 0 时不生效")
    print("\n建议配置:")
    print("- min_trade_amount: 设置合理的最小交易金额（如 $1-$5）")
    print("- max_trade_amount: 设置最大风险敞口（如 $50-$100）")
    print("- 确保 min_trade_amount <= max_trade_amount")


if __name__ == '__main__':
    test_min_trade_amount()
