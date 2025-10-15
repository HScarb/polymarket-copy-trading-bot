#!/usr/bin/env python3
"""测试代理模式配置"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(__file__))

from src.config_loader import load_config

def test_proxy_config():
    """测试代理配置加载"""
    try:
        print("Loading config...")
        config = load_config()

        print("\n=== Configuration Test ===")

        # 检查用户钱包配置
        if 'user_wallets' not in config or not config['user_wallets']:
            print("ERROR: No user wallets configured")
            return False

        wallet = config['user_wallets'][0]

        print(f"\nWallet Configuration:")
        print(f"  Name: {wallet['name']}")
        print(f"  Address: {wallet['address']}")
        print(f"  Proxy Address: {wallet.get('proxy_address', 'NOT SET')}")
        print(f"  Signature Type: {wallet.get('signature_type', 0)}")
        print(f"  Private Key Env: {wallet.get('private_key_env', 'NOT SET')}")

        # 验证代理模式配置
        sig_type = wallet.get('signature_type', 0)
        proxy_addr = wallet.get('proxy_address')

        if sig_type == 2:
            if not proxy_addr:
                print("\nERROR: signature_type=2 requires proxy_address")
                return False
            print(f"\nSUCCESS: Proxy mode configured correctly")
            print(f"  - EOA Wallet: {wallet['address']}")
            print(f"  - Proxy Contract (Funder): {proxy_addr}")
        elif sig_type == 0:
            print(f"\nINFO: Using standard EOA mode (signature_type=0)")
        else:
            print(f"\nWARNING: Unexpected signature_type: {sig_type}")

        # 检查私钥环境变量
        env_var = wallet.get('private_key_env')
        if env_var:
            if os.environ.get(env_var):
                print(f"  - Private key environment variable '{env_var}' is SET")
            else:
                print(f"  - WARNING: Private key environment variable '{env_var}' is NOT SET")

        print("\n=== Test PASSED ===")
        return True

    except Exception as e:
        print(f"\n=== Test FAILED ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_proxy_config()
    sys.exit(0 if success else 1)
