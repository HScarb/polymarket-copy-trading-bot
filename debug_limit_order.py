#!/usr/bin/env python3
"""
调试限价单工具

用于测试代理模式下的限价单创建功能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.config_loader import load_config
from src.copy_trader import CopyTrader
from src.in_memory_activity_queue import InMemoryActivityQueue
from src.logger import log


def debug_create_limit_order(
    condition_id: str,
    outcome: str,
    side: str,
    amount: float,
    price: float
):
    """
    调试限价单创建

    Args:
        condition_id: 市场条件ID
        outcome: 结果 (YES/NO 或具体选项名)
        side: 交易方向 (BUY/SELL)
        amount: 交易金额 (USDC)
        price: 限价 (0.0-1.0)
    """
    try:
        print("=" * 60)
        print("限价单调试工具")
        print("=" * 60)
        print()

        # 加载配置
        print("1. 加载配置...")
        config = load_config()

        if 'user_wallets' not in config or not config['user_wallets']:
            print("ERROR: 配置文件中没有 user_wallets")
            return False

        wallet_config = config['user_wallets'][0]
        print(f"   钱包: {wallet_config['name']}")
        print(f"   地址: {wallet_config['address']}")
        print(f"   Signature Type: {wallet_config.get('signature_type', 0)}")
        if wallet_config.get('signature_type') == 2:
            print(f"   Proxy: {wallet_config.get('proxy_address')}")
        print()

        # 创建临时 ActivityQueue (不会实际使用)
        activity_queue = InMemoryActivityQueue(max_workers=1)

        # 初始化 CopyTrader
        print("2. 初始化 CopyTrader...")

        # 从配置获取 Polygon RPC 配置
        polygon_rpc_config = config.get('polygon_rpc')

        copy_trader = CopyTrader(
            wallet_config=wallet_config,
            activity_queue=activity_queue,
            polygon_rpc_config=polygon_rpc_config
        )
        print("   CopyTrader 初始化成功")
        print()

        # 获取 token_id
        print("3. 获取市场信息...")
        print(f"   Condition ID: {condition_id}")
        print(f"   Outcome: {outcome}")

        token_id = copy_trader._get_token_id(condition_id, outcome)

        if not token_id:
            print(f"   ERROR: 无法获取 token_id for outcome '{outcome}'")
            print(f"   请检查 condition_id 和 outcome 是否正确")
            return False

        print(f"   Token ID: {token_id}")
        print()

        # 创建限价单
        print("4. 创建限价单...")
        print(f"   方向: {side}")
        print(f"   金额: ${amount:.2f} USDC")
        print(f"   价格: {price}")
        print()

        result = copy_trader._execute_limit_order(
            token_id=token_id,
            side=side.upper(),
            size=amount,
            price=price
        )

        print("=" * 60)
        print("SUCCESS: 限价单创建成功!")
        print("=" * 60)
        print()
        print("订单详情:")
        print(f"  Order ID: {result.get('orderID', 'N/A')}")
        print(f"  Status: {result.get('status', 'N/A')}")

        # 打印完整响应 (用于调试)
        if result:
            print()
            print("完整响应:")
            import json
            print(json.dumps(result, indent=2))

        return True

    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR: 限价单创建失败")
        print("=" * 60)
        print(f"错误信息: {e}")
        print()

        import traceback
        print("详细堆栈:")
        traceback.print_exc()

        return False


def main():
    """主函数 - 解析命令行参数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='调试限价单创建工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 创建一个 BUY 限价单
  python debug_limit_order.py \\
    --condition-id "0x0132301805f663ea09e2b9b6baed5c4d20e876f0f6e33d7cdabbe85c0e39b574" \\
    --outcome "YES" \\
    --side "BUY" \\
    --amount 2.0 \\
    --price 0.65

  # 创建一个 SELL 限价单
  python debug_limit_order.py \\
    --condition-id "0x0132301805f663ea09e2b9b6baed5c4d20e876f0f6e33d7cdabbe85c0e39b574" \\
    --outcome "YES" \\
    --side "SELL" \\
    --amount 1.5 \\
    --price 0.70
'''
    )

    parser.add_argument(
        '--condition-id',
        required=True,
        help='市场条件ID (condition_id)'
    )

    parser.add_argument(
        '--outcome',
        required=True,
        help='结果 (YES/NO 或具体选项名)'
    )

    parser.add_argument(
        '--side',
        required=True,
        choices=['BUY', 'SELL', 'buy', 'sell'],
        help='交易方向'
    )

    parser.add_argument(
        '--amount',
        type=float,
        required=True,
        help='交易金额 (USDC)'
    )

    parser.add_argument(
        '--price',
        type=float,
        required=True,
        help='限价 (0.0 - 1.0)'
    )

    args = parser.parse_args()

    # 验证参数
    if args.amount <= 0:
        print("ERROR: amount 必须大于 0")
        sys.exit(1)

    if args.price < 0 or args.price > 1:
        print("ERROR: price 必须在 0.0 和 1.0 之间")
        sys.exit(1)

    # 执行调试
    success = debug_create_limit_order(
        condition_id=args.condition_id,
        outcome=args.outcome,
        side=args.side.upper(),
        amount=args.amount,
        price=args.price
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
