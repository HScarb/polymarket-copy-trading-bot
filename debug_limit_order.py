#!/usr/bin/env python3
"""
Debug tool for limit orders.

Used to test limit order creation in proxy mode.
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
    Debug limit order creation.

    Args:
        condition_id: Market condition ID
        outcome: Outcome (YES/NO or specific option name)
        side: Trade direction (BUY/SELL)
        amount: Trade amount (USDC)
        price: Limit price (0.0-1.0)
    """
    try:
        print("=" * 60)
        print("Limit Order Debug Tool")
        print("=" * 60)
        print()

        # Load configuration
        print("1. Loading configuration...")
        config = load_config()

        if 'user_wallets' not in config or not config['user_wallets']:
            print("ERROR: No user_wallets in configuration file")
            return False

        wallet_config = config['user_wallets'][0]
        print(f"   Wallet: {wallet_config['name']}")
        print(f"   Address: {wallet_config['address']}")
        print(f"   Signature Type: {wallet_config.get('signature_type', 0)}")
        if wallet_config.get('signature_type') == 2:
            print(f"   Proxy: {wallet_config.get('proxy_address')}")
        print()

        # Create temporary ActivityQueue (won't actually be used)
        activity_queue = InMemoryActivityQueue(max_workers=1)

        # Initialize CopyTrader
        print("2. Initializing CopyTrader...")

        # Get Polygon RPC configuration from config
        polygon_rpc_config = config.get('polygon_rpc')

        copy_trader = CopyTrader(
            wallet_config=wallet_config,
            activity_queue=activity_queue,
            polygon_rpc_config=polygon_rpc_config
        )
        print("   CopyTrader initialized successfully")
        print()

        # Get token_id (now using order_executor)
        print("3. Getting market information...")
        print(f"   Condition ID: {condition_id}")
        print(f"   Outcome: {outcome}")

        token_id = copy_trader.order_executor.get_token_id(condition_id, outcome)

        if not token_id:
            print(f"   ERROR: Cannot get token_id for outcome '{outcome}'")
            print(f"   Please check if condition_id and outcome are correct")
            return False

        print(f"   Token ID: {token_id}")
        print()

        # Create limit order (now using order_executor)
        print("4. Creating limit order...")
        print(f"   Side: {side}")
        print(f"   Amount: ${amount:.2f} USDC")
        print(f"   Price: {price}")
        print()

        result = copy_trader.order_executor.execute_limit_order(
            token_id=token_id,
            side=side.upper(),
            size=amount,
            price=price
        )

        print("=" * 60)
        print("SUCCESS: Limit order created successfully!")
        print("=" * 60)
        print()
        print("Order details:")
        print(f"  Order ID: {result.get('orderID', 'N/A')}")
        print(f"  Status: {result.get('status', 'N/A')}")

        # Print full response (for debugging)
        if result:
            print()
            print("Full response:")
            import json
            print(json.dumps(result, indent=2))

        return True

    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR: Limit order creation failed")
        print("=" * 60)
        print(f"Error message: {e}")
        print()

        import traceback
        print("Detailed stack trace:")
        traceback.print_exc()

        return False


def main():
    """Main function - parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Debug tool for limit order creation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Create a BUY limit order
  python debug_limit_order.py \\
    --condition-id "0x0132301805f663ea09e2b9b6baed5c4d20e876f0f6e33d7cdabbe85c0e39b574" \\
    --outcome "YES" \\
    --side "BUY" \\
    --amount 2.0 \\
    --price 0.65

  # Create a SELL limit order
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
        help='Market condition ID'
    )

    parser.add_argument(
        '--outcome',
        required=True,
        help='Outcome (YES/NO or specific option name)'
    )

    parser.add_argument(
        '--side',
        required=True,
        choices=['BUY', 'SELL', 'buy', 'sell'],
        help='Trade direction'
    )

    parser.add_argument(
        '--amount',
        type=float,
        required=True,
        help='Trade amount (USDC)'
    )

    parser.add_argument(
        '--price',
        type=float,
        required=True,
        help='Limit price (0.0 - 1.0)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.amount <= 0:
        print("ERROR: amount must be greater than 0")
        sys.exit(1)

    if args.price < 0 or args.price > 1:
        print("ERROR: price must be between 0.0 and 1.0")
        sys.exit(1)

    # Execute debug
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
