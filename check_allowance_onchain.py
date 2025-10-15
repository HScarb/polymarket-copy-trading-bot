#!/usr/bin/env python3
"""直接检查链上的 allowance 状态（不通过 API）"""

import sys
from web3 import Web3

# Polygon 配置
POLYGON_RPC_URL = "https://polygon-rpc.com"
CHAIN_ID = 137

# 合约地址
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# 交易所合约地址
EXCHANGE_ADDRESSES = [
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
]

# ERC20 ABI (只需要 allowance 和 balanceOf)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# ERC1155 ABI
ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

def check_onchain_allowances():
    """检查链上的授权状态"""
    print("=== 链上 Allowance 检查 ===\n")

    # 您的地址
    EOA_ADDRESS = "0x7c194708d0b203b00c57c001cda31eeb8e961aa7"
    PROXY_ADDRESS = "0x2173D82638Bd32328cc3A1118408A2a577ea2869"

    print(f"EOA 地址: {EOA_ADDRESS}")
    print(f"Proxy 地址: {PROXY_ADDRESS}\n")

    # 连接到 Polygon
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))

    if not w3.is_connected():
        print("ERROR: 无法连接到 Polygon 网络")
        return False

    print(f"Connected to Polygon (Chain ID: {w3.eth.chain_id})\n")

    # 创建合约实例
    usdc_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=ERC20_ABI
    )

    ct_contract = w3.eth.contract(
        address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
        abi=ERC1155_ABI
    )

    # 检查两个地址
    for addr_name, address in [("EOA", EOA_ADDRESS), ("Proxy", PROXY_ADDRESS)]:
        print(f"{'='*60}")
        print(f"检查 {addr_name} 地址: {address}")
        print(f"{'='*60}\n")

        checksum_addr = Web3.to_checksum_address(address)

        # 1. 检查 USDC 余额
        try:
            balance_raw = usdc_contract.functions.balanceOf(checksum_addr).call()
            balance = balance_raw / 1_000_000
            print(f"USDC 余额: ${balance:.2f}\n")
        except Exception as e:
            print(f"ERROR: 查询余额失败: {e}\n")
            balance = 0

        # 2. 检查 USDC 授权
        print("USDC Allowances (授权给交易所):")
        has_usdc_allowance = False
        for i, exchange in enumerate(EXCHANGE_ADDRESSES, 1):
            try:
                checksum_exchange = Web3.to_checksum_address(exchange)
                allowance_raw = usdc_contract.functions.allowance(
                    checksum_addr,
                    checksum_exchange
                ).call()
                allowance = allowance_raw / 1_000_000

                status = "[OK] Approved" if allowance > 0 else "[NO] Not approved"
                print(f"  Exchange {i}: {status} (${allowance:.2f})")

                if allowance > 0:
                    has_usdc_allowance = True
            except Exception as e:
                print(f"  Exchange {i}: ERROR - {e}")

        print()

        # 3. 检查 Conditional Tokens 授权
        print("Conditional Tokens Approvals (授权给交易所):")
        has_ct_approval = False
        for i, exchange in enumerate(EXCHANGE_ADDRESSES, 1):
            try:
                checksum_exchange = Web3.to_checksum_address(exchange)
                is_approved = ct_contract.functions.isApprovedForAll(
                    checksum_addr,
                    checksum_exchange
                ).call()

                status = "[OK] Approved" if is_approved else "[NO] Not approved"
                print(f"  Exchange {i}: {status}")

                if is_approved:
                    has_ct_approval = True
            except Exception as e:
                print(f"  Exchange {i}: ERROR - {e}")

        print()

        # 总结
        if balance > 0:
            if has_usdc_allowance and has_ct_approval:
                print(f"[OK] {addr_name} address is fully configured and ready to trade")
            elif not has_usdc_allowance and not has_ct_approval:
                print(f"[NO] {addr_name} address NOT approved, need to Enable Trading")
            else:
                print(f"[WARN] {addr_name} address partially approved, recommend re-Enable Trading")
        else:
            print(f"[INFO] {addr_name} address has zero balance, no approval needed")

        print()

    print(f"{'='*60}")
    print("结论:")
    print(f"{'='*60}")
    print("\n对于 signature_type=2（代理模式）:")
    print("- 资金应该在 Proxy 地址")
    print("- 授权也应该由 Proxy 地址完成")
    print("- 在 Polymarket 网站上连接钱包时，应该显示 Proxy 地址")
    print("\n如果您的资金在 EOA 地址:")
    print("- 考虑使用 signature_type=0（EOA 模式）")
    print("- 或者将资金转移到 Polymarket（会自动使用 Proxy）")

    return True

if __name__ == "__main__":
    try:
        success = check_onchain_allowances()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
