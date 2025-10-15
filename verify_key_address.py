#!/usr/bin/env python3
"""
验证私钥和地址匹配

检查 SCARB4_PRIVATE_KEY 环境变量中的私钥是否对应配置文件中的 EOA 地址
"""

import sys
import os
from eth_account import Account

# 加载.env文件
from dotenv import load_dotenv
load_dotenv()

# 从环境变量读取私钥
private_key = os.environ.get('SCARB4_PRIVATE_KEY')

if not private_key:
    print("ERROR: 环境变量 SCARB4_PRIVATE_KEY 未设置")
    sys.exit(1)

# 从私钥派生地址
try:
    account = Account.from_key(private_key)
    derived_address = account.address

    print("=" * 60)
    print("私钥地址验证")
    print("=" * 60)
    print()
    print(f"从私钥派生的地址: {derived_address}")
    print()
    print("配置文件中的地址:")
    print(f"  EOA 地址:   0x7c194708d0b203b00c57c001cda31eeb8e961aa7")
    print(f"  Proxy 地址: 0x2173D82638Bd32328cc3A1118408A2a577ea2869")
    print()

    # 检查匹配
    config_eoa = "0x7c194708d0b203b00c57c001cda31eeb8e961aa7".lower()
    config_proxy = "0x2173D82638Bd32328cc3A1118408A2a577ea2869".lower()

    if derived_address.lower() == config_eoa:
        print("✓ 私钥匹配 EOA 地址 - 正确!")
        print()
        print("建议配置:")
        print("  signature_type: 2")
        print("  address: 0x7c194708d0b203b00c57c001cda31eeb8e961aa7  (EOA)")
        print("  proxy_address: 0x2173D82638Bd32328cc3A1118408A2a577ea2869  (Funder)")
    elif derived_address.lower() == config_proxy:
        print("✓ 私钥匹配 Proxy 地址")
        print()
        print("ERROR: 这不正常!")
        print("Proxy 地址不应该有对应的私钥，它是一个智能合约。")
        print("请检查你的配置。")
    else:
        print("✗ 私钥不匹配任何配置的地址!")
        print()
        print(f"私钥对应地址: {derived_address}")
        print(f"EOA 地址:      {config_eoa}")
        print(f"Proxy 地址:    {config_proxy}")
        print()
        print("请检查：")
        print("1. 环境变量 SCARB4_PRIVATE_KEY 是否设置正确")
        print("2. config.yaml 中的 address 和 proxy_address 是否正确")

    print()
    print("=" * 60)

except Exception as e:
    print(f"ERROR: 无法处理私钥: {e}")
    sys.exit(1)
