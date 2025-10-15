#!/usr/bin/env python3
"""测试代理模式的 API allowance 设置"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams
from src.config_loader import load_config, load_private_key

def test_api_allowance():
    """测试 API allowance 查询和设置"""
    try:
        print("Loading config...")
        config = load_config()

        # 获取第一个钱包配置
        if 'user_wallets' not in config or not config['user_wallets']:
            print("ERROR: No user wallets configured")
            return False

        wallet = config['user_wallets'][0]

        print("\n=== Wallet Configuration ===")
        print(f"Name: {wallet['name']}")
        print(f"Address: {wallet['address']}")
        print(f"Signature Type: {wallet.get('signature_type', 0)}")
        print(f"Proxy Address: {wallet.get('proxy_address', 'N/A')}")

        # 加载私钥
        private_key = load_private_key(wallet)
        print(f"Private Key: {'*' * 40} (loaded)")

        # 初始化 CLOB 客户端
        print("\n=== Initializing ClobClient ===")
        client_params = {
            'host': 'https://clob.polymarket.com',
            'key': private_key,
            'chain_id': 137,
            'signature_type': wallet.get('signature_type', 0),
        }

        # 如果是代理模式，添加 funder 参数
        if wallet.get('signature_type') == 2:
            client_params['funder'] = wallet['proxy_address']
            print(f"Using proxy mode with funder: {wallet['proxy_address']}")

        client = ClobClient(**client_params)

        # 设置 API credentials
        print("Setting API credentials...")
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print("API credentials set successfully")

        # 查询当前 balance 和 allowance
        print("\n=== Checking Balance and Allowance ===")
        params = BalanceAllowanceParams(
            asset_type="COLLATERAL",
            signature_type=wallet.get('signature_type', 0)
        )

        result = client.get_balance_allowance(params)

        balance_raw = result.get('balance', 0)
        allowance_raw = result.get('allowance', 0)

        balance = float(balance_raw) / 1_000_000
        allowance = float(allowance_raw) / 1_000_000

        print(f"Current Balance: ${balance:.2f} USDC")
        print(f"Current Allowance: ${allowance:.2f} USDC")

        # 如果是代理模式，检查并提供指导
        if wallet.get('signature_type') == 2:
            print("\n=== Proxy Mode Allowance Check ===")

            if allowance == 0:
                print("\nWARNING: Allowance is 0!")
                print("\nFor proxy mode (signature_type=2), allowances MUST be set on-chain")
                print("through the Polymarket website. The API cannot set them programmatically.")
                print("\nPlease follow these steps:")
                print("1. Visit https://polymarket.com")
                print(f"2. Connect your OKX wallet (address: {wallet['address']})")
                print("3. Click 'Enable Trading' button on any trading page")
                print("4. Confirm the approval transactions (USDC + Conditional Tokens)")
                print("5. Wait for transactions to confirm")
                print("6. Re-run this test script to verify")
                print("\nAfter completing these steps, the allowance should be > 0")
                return False

            elif allowance > 0 and allowance >= balance * 0.9:
                print(f"SUCCESS: Allowance is sufficient (${allowance:.2f} >= ${balance:.2f})")
                print("Your proxy wallet is ready for trading!")

                # 尝试同步 API allowance
                print("\nSyncing API allowance state...")
                client.update_balance_allowance(params)
                print("API allowance state synced")

            else:
                print(f"INFO: Allowance is low (${allowance:.2f}) but not zero")
                print("This may be sufficient for small trades, but consider re-enabling trading")
                print("on Polymarket website if you encounter issues")

                # 尝试同步
                print("\nSyncing API allowance state...")
                client.update_balance_allowance(params)

                result_after = client.get_balance_allowance(params)
                new_allowance_raw = result_after.get('allowance', 0)
                new_allowance = float(new_allowance_raw) / 1_000_000
                print(f"Allowance after sync: ${new_allowance:.2f}")

        else:
            print("\nINFO: Not in proxy mode (signature_type != 2)")
            print("For EOA mode (signature_type=0), allowances are set on-chain via Web3")

        print("\n=== Test PASSED ===")
        return True

    except Exception as e:
        print(f"\n=== Test FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_api_allowance()
    sys.exit(0 if success else 1)
