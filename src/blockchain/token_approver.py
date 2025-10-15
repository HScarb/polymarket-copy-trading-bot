"""
Token approval utilities for Polygon network.

Handles USDC (ERC20) and Conditional Tokens (ERC1155) approvals
for Polymarket exchange contracts.
"""

import os
import warnings
from typing import Optional, Dict, List

import requests
from web3 import Web3

from src.logger import log

# Suppress SSL verification warnings when using corporate proxy
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Polygon network configuration
POLYGON_RPC_URL = "https://polygon-rpc.com"
CHAIN_ID = 137

# Token contract addresses
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# Exchange contract addresses (approval targets)
EXCHANGE_ADDRESSES = [
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
]

# Infinite allowance amount
INFINITE_ALLOWANCE = 2**256 - 1

# ERC20 ABI (approve and allowance methods only)
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

# ERC1155 ABI (setApprovalForAll and isApprovedForAll methods only)
ERC1155_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_operator", "type": "address"},
            {"name": "_approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "type": "function"
    },
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


class TokenApprover:
    """
    Handles token approvals for Polymarket trading.

    Manages USDC (ERC20) and Conditional Tokens (ERC1155) approvals
    for exchange contracts on Polygon network.
    """

    def __init__(
        self,
        address: str,
        private_key: str,
        name: str = "Wallet",
        polygon_rpc_config: Optional[Dict] = None
    ):
        """
        Initialize token approver.

        Args:
            address: Wallet address
            private_key: Private key for signing transactions
            name: Wallet name for logging
            polygon_rpc_config: Polygon RPC configuration (url, proxy, verify_ssl)
        """
        self.address = address
        self.private_key = private_key
        self.name = name
        self.w3 = self._init_web3(polygon_rpc_config)

    def _init_web3(self, polygon_rpc_config: Optional[Dict]) -> Optional[Web3]:
        """Initialize Web3 client with proxy and SSL configuration."""
        try:
            rpc_url = POLYGON_RPC_URL
            proxy = None
            verify_ssl = True

            if polygon_rpc_config:
                rpc_url = polygon_rpc_config.get('url', POLYGON_RPC_URL)
                proxy = polygon_rpc_config.get('proxy')
                verify_ssl = polygon_rpc_config.get('verify_ssl', True)
                if not proxy:
                    proxy = os.environ.get('POLYGON_RPC_PROXY')
            else:
                proxy = os.environ.get('POLYGON_RPC_PROXY')

            # Check environment variable for SSL verification
            env_verify_ssl = os.environ.get('POLYGON_RPC_VERIFY_SSL', '').lower()
            if env_verify_ssl in ('false', '0'):
                verify_ssl = False
            elif env_verify_ssl in ('true', '1'):
                verify_ssl = True

            # Create custom Session with SSL verification settings
            session = requests.Session()
            session.verify = verify_ssl

            # Configure HTTPProvider request parameters
            request_kwargs = {'timeout': 60 if proxy else 30}

            if proxy:
                session.proxies = {
                    'http': proxy,
                    'https': proxy
                }
                log.info(f"[{self.name}] Using proxy for Polygon RPC: {proxy} (SSL verify: {verify_ssl})")

            # Create Web3 instance with custom session
            provider = Web3.HTTPProvider(rpc_url, request_kwargs=request_kwargs, session=session)
            w3 = Web3(provider)

            if not w3.is_connected():
                log.warning(f"[{self.name}] Cannot connect to Polygon network, token approval features may be unavailable")

            return w3

        except Exception as e:
            log.warning(f"[{self.name}] Failed to initialize Web3 client: {e}")
            return None

    def ensure_approvals(self) -> None:
        """
        Check and ensure all necessary token approvals are set.

        For trading, we need to approve:
        1. USDC (ERC20) for three exchange contracts
        2. Conditional Tokens (ERC1155) for three exchange contracts
        """
        if not self.w3 or not self.w3.is_connected():
            log.warning(f"[{self.name}] Web3 not connected, skipping token approval check")
            return

        log.info(f"[{self.name}] Checking token approval status...")

        try:
            self._ensure_usdc_approvals()
            self._ensure_conditional_tokens_approvals()
            log.info(f"[{self.name}] ✓ All token approvals ready")

        except Exception as e:
            log.error(f"[{self.name}] Token approval check failed: {e}", exc_info=True)
            raise

    def _ensure_usdc_approvals(self) -> None:
        """Check and approve USDC (ERC20) for all exchange contracts."""
        usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI
        )

        for exchange_address in EXCHANGE_ADDRESSES:
            self._approve_erc20(usdc_contract, exchange_address, "USDC")

    def _ensure_conditional_tokens_approvals(self) -> None:
        """Check and approve Conditional Tokens (ERC1155) for all exchange contracts."""
        ct_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
            abi=ERC1155_ABI
        )

        for exchange_address in EXCHANGE_ADDRESSES:
            self._approve_erc1155(ct_contract, exchange_address, "Conditional Tokens")

    def _approve_erc20(self, contract, spender_address: str, token_name: str) -> None:
        """Approve ERC20 token for a spender contract."""
        try:
            checksum_spender = Web3.to_checksum_address(spender_address)
            checksum_owner = Web3.to_checksum_address(self.address)

            # Check current allowance
            current_allowance = contract.functions.allowance(
                checksum_owner,
                checksum_spender
            ).call()

            if current_allowance >= INFINITE_ALLOWANCE // 2:
                log.debug(
                    f"[{self.name}] {token_name} already approved for {spender_address[:10]}... "
                    f"(allowance: {current_allowance})"
                )
                return

            # Need to approve
            log.info(
                f"[{self.name}] Approving {token_name} for exchange {spender_address[:10]}..."
            )

            # Build approval transaction
            approve_txn = contract.functions.approve(
                checksum_spender,
                INFINITE_ALLOWANCE
            ).build_transaction({
                'from': checksum_owner,
                'nonce': self.w3.eth.get_transaction_count(checksum_owner),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': CHAIN_ID
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                approve_txn,
                private_key=self.private_key
            )

            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            log.info(f"[{self.name}] {token_name} approval transaction submitted: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                log.info(f"[{self.name}] ✓ {token_name} approval successful: {spender_address[:10]}...")
            else:
                raise Exception(f"{token_name} approval transaction failed: {tx_hash.hex()}")

        except Exception as e:
            log.error(
                f"[{self.name}] Error approving {token_name} for {spender_address}: {e}",
                exc_info=True
            )
            raise

    def _approve_erc1155(self, contract, operator_address: str, token_name: str) -> None:
        """Approve ERC1155 token for an operator contract."""
        try:
            checksum_operator = Web3.to_checksum_address(operator_address)
            checksum_owner = Web3.to_checksum_address(self.address)

            # Check if already approved
            is_approved = contract.functions.isApprovedForAll(
                checksum_owner,
                checksum_operator
            ).call()

            if is_approved:
                log.debug(
                    f"[{self.name}] {token_name} already approved for {operator_address[:10]}..."
                )
                return

            # Need to approve
            log.info(
                f"[{self.name}] Approving {token_name} for exchange {operator_address[:10]}..."
            )

            # Build approval transaction
            approve_txn = contract.functions.setApprovalForAll(
                checksum_operator,
                True
            ).build_transaction({
                'from': checksum_owner,
                'nonce': self.w3.eth.get_transaction_count(checksum_owner),
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'chainId': CHAIN_ID
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                approve_txn,
                private_key=self.private_key
            )

            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            log.info(f"[{self.name}] {token_name} approval transaction submitted: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                log.info(f"[{self.name}] ✓ {token_name} approval successful: {operator_address[:10]}...")
            else:
                raise Exception(f"{token_name} approval transaction failed: {tx_hash.hex()}")

        except Exception as e:
            log.error(
                f"[{self.name}] Error approving {token_name} for {operator_address}: {e}",
                exc_info=True
            )
            raise
