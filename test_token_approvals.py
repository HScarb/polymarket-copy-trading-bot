"""
测试代币授权功能

此脚本验证：
1. Web3 客户端能够正确连接到 Polygon 网络
2. 能够查询 USDC 和 Conditional Tokens 的授权状态
3. CopyTrader 初始化时正确检查和设置授权
"""

import os
from dotenv import load_dotenv
from web3 import Web3

# 加载环境变量
load_dotenv()

# 从 copy_trader.py 导入常量
from src.copy_trader import (
    POLYGON_RPC_URL,
    USDC_ADDRESS,
    CONDITIONAL_TOKENS_ADDRESS,
    EXCHANGE_ADDRESSES,
    ERC20_ABI,
    ERC1155_ABI
)

def test_web3_connection():
    """测试 Web3 连接"""
    print("=" * 60)
    print("测试 1: Web3 连接到 Polygon 网络")
    print("=" * 60)

    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))

    if w3.is_connected():
        print(f"✓ 成功连接到 Polygon 网络")
        print(f"  Chain ID: {w3.eth.chain_id}")
        print(f"  Latest Block: {w3.eth.block_number}")
        return w3
    else:
        print(f"✗ 无法连接到 Polygon 网络")
        return None

def test_usdc_allowances(w3, wallet_address):
    """测试 USDC 授权状态"""
    print("\n" + "=" * 60)
    print("测试 2: 查询 USDC 授权状态")
    print("=" * 60)

    usdc_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI
    )

    print(f"USDC 合约地址: {USDC_ADDRESS}")
    print(f"钱包地址: {wallet_address}")
    print()

    for i, exchange_address in enumerate(EXCHANGE_ADDRESSES, 1):
        try:
            allowance = usdc_contract.functions.allowance(
                Web3.to_checksum_address(wallet_address),
                Web3.to_checksum_address(exchange_address)
            ).call()

            if allowance > 0:
                print(f"  [{i}] {exchange_address[:10]}... ✓ 已授权 (额度: {allowance})")
            else:
                print(f"  [{i}] {exchange_address[:10]}... ✗ 未授权 (额度: 0)")
        except Exception as e:
            print(f"  [{i}] {exchange_address[:10]}... ✗ 查询失败: {e}")

def test_conditional_tokens_allowances(w3, wallet_address):
    """测试 Conditional Tokens 授权状态"""
    print("\n" + "=" * 60)
    print("测试 3: 查询 Conditional Tokens 授权状态")
    print("=" * 60)

    ct_contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
        abi=ERC1155_ABI
    )

    print(f"Conditional Tokens 合约地址: {CONDITIONAL_TOKENS_ADDRESS}")
    print(f"钱包地址: {wallet_address}")
    print()

    for i, exchange_address in enumerate(EXCHANGE_ADDRESSES, 1):
        try:
            is_approved = ct_contract.functions.isApprovedForAll(
                Web3.to_checksum_address(wallet_address),
                Web3.to_checksum_address(exchange_address)
            ).call()

            if is_approved:
                print(f"  [{i}] {exchange_address[:10]}... ✓ 已授权")
            else:
                print(f"  [{i}] {exchange_address[:10]}... ✗ 未授权")
        except Exception as e:
            print(f"  [{i}] {exchange_address[:10]}... ✗ 查询失败: {e}")

def test_copy_trader_initialization():
    """测试 CopyTrader 初始化和授权检查"""
    print("\n" + "=" * 60)
    print("测试 4: CopyTrader 初始化和授权检查")
    print("=" * 60)

    try:
        from src.config_loader import load_config
        from src.in_memory_activity_queue import InMemoryActivityQueue
        from src.copy_trader import CopyTrader

        # 加载配置
        config = load_config("config.yaml")
        user_wallets = config.get('user_wallets', [])

        if not user_wallets:
            print("✗ 配置文件中未找到用户钱包配置")
            return

        # 创建活动队列
        activity_queue = InMemoryActivityQueue(max_workers=1)

        # 初始化第一个钱包的 CopyTrader
        wallet_config = user_wallets[0]
        print(f"正在初始化钱包: {wallet_config['name']} ({wallet_config['address']})")
        print()

        trader = CopyTrader(
            wallet_config=wallet_config,
            activity_queue=activity_queue
        )

        print("\n✓ CopyTrader 初始化成功")
        print(f"  钱包名称: {trader.name}")
        print(f"  钱包地址: {trader.address}")
        print(f"  复制模式: {trader.strategy_config['copy_mode']}")

    except Exception as e:
        print(f"\n✗ CopyTrader 初始化失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("开始测试代币授权功能")
    print("=" * 60)

    # 测试 1: Web3 连接
    w3 = test_web3_connection()
    if not w3:
        print("\n✗ Web3 连接失败，无法继续测试")
        return

    # 从配置文件获取钱包地址
    try:
        from src.config_loader import load_config
        config = load_config("config.yaml")
        user_wallets = config.get('user_wallets', [])

        if not user_wallets:
            print("\n✗ 配置文件中未找到用户钱包配置")
            return

        wallet_address = user_wallets[0]['address']

        # 测试 2: USDC 授权状态
        test_usdc_allowances(w3, wallet_address)

        # 测试 3: Conditional Tokens 授权状态
        test_conditional_tokens_allowances(w3, wallet_address)

        # 测试 4: CopyTrader 初始化
        test_copy_trader_initialization()

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
