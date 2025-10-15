"""
Copy trading core module.

Provides automated copy trading functionality that listens to
target wallet activities and executes trades based on configured strategies.
"""

import time
from functools import partial
from typing import List, Optional, Dict, Any

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams

from src.activity_queue import ActivityQueue
from src.config_loader import load_private_key
from src.logger import log
from src.blockchain.token_approver import TokenApprover
from src.trading.order_executor import OrderExecutor, OrderExecutionError
from src.utils.activity_logger import get_trade_value


class CopyTraderError(Exception):
    """Base exception for copy trading."""
    pass


class InsufficientBalanceError(CopyTraderError):
    """Insufficient balance exception."""
    pass


class NetworkError(CopyTraderError):
    """Network error exception."""
    pass


class CopyTrader:
    """
    Copy trading core class.

    Features:
    1. Subscribe to target wallet trading activities from ActivityQueue
    2. Filter and calculate trade sizes based on configured strategy
    3. Execute trades using py-clob-client
    4. Provide error handling and retry mechanisms
    """

    def __init__(
        self,
        wallet_config: dict,
        activity_queue: ActivityQueue,
        chain_id: int = 137,  # Polygon mainnet
        host: str = "https://clob.polymarket.com",
        polygon_rpc_config: Optional[Dict] = None
    ):
        """
        Initialize copy trader.

        Args:
            wallet_config: User wallet config (includes address, private key source, strategy, etc.)
            activity_queue: Activity queue instance
            chain_id: Blockchain ID, default 137 (Polygon mainnet)
            host: CLOB API host address
            polygon_rpc_config: Polygon RPC config (includes url and proxy)
        """
        self.name = wallet_config['name']
        self.address = wallet_config['address']
        self.strategy_config = wallet_config['copy_strategy']
        self.activity_queue = activity_queue

        # Get signature type and proxy address configuration
        self.signature_type = wallet_config.get('signature_type', 0)  # Default EOA mode
        self.proxy_address = wallet_config.get('proxy_address')  # Proxy contract address (funder)

        # Securely load private key
        private_key = load_private_key(wallet_config)
        self.private_key = private_key

        # Initialize token approver (for EOA mode only)
        self.token_approver = None
        if self.signature_type == 0:
            # EOA mode: requires on-chain token approvals
            self.token_approver = TokenApprover(
                address=self.address,
                private_key=private_key,
                name=self.name,
                polygon_rpc_config=polygon_rpc_config
            )
            try:
                self.token_approver.ensure_approvals()
            except Exception as e:
                log.warning(f"[{self.name}] Token approval failed: {e}")
        else:
            log.info(f"[{self.name}] Proxy mode skips on-chain token approval (managed by Polymarket)")

        # Initialize CLOB client
        self.clob_client = self._init_clob_client(host, chain_id, private_key)

        # Initialize order executor
        self.order_executor = OrderExecutor(
            clob_client=self.clob_client,
            wallet_name=self.name,
            signature_type=self.signature_type
        )

        # Query and print balance
        self._log_balance()

        # For proxy mode, set API allowance
        if self.signature_type == 2:
            self._ensure_api_allowance()

        # Trading statistics
        self.stats = {
            'total_activities': 0,
            'filtered_out': 0,
            'trades_attempted': 0,
            'trades_succeeded': 0,
            'trades_failed': 0
        }

    def _init_clob_client(self, host: str, chain_id: int, private_key: str) -> ClobClient:
        """Initialize CLOB client with appropriate signature type."""
        try:
            client_params = {
                'host': host,
                'key': private_key,
                'chain_id': chain_id,
                'signature_type': self.signature_type,
            }

            # If proxy mode, need to specify funder address
            if self.signature_type == 2:
                if not self.proxy_address:
                    raise ValueError(
                        f"Wallet '{self.name}' uses signature_type=2 (proxy mode), "
                        f"must configure proxy_address (proxy contract address)"
                    )
                client_params['funder'] = self.proxy_address
                log.info(
                    f"[{self.name}] Using proxy mode | "
                    f"EOA: {self.address} | "
                    f"Funder: {self.proxy_address}"
                )
            else:
                log.info(f"[{self.name}] Using EOA direct signing mode")

            clob_client = ClobClient(**client_params)

            # Create or derive API credentials (required for Level 2 authentication)
            try:
                creds = clob_client.create_or_derive_api_creds()
                clob_client.set_api_creds(creds)
                log.info(f"CopyTrader '{self.name}' API credentials set")
            except Exception as e:
                log.warning(f"Failed to set API credentials: {e}, some features may be unavailable")

            log.info(
                f"CopyTrader '{self.name}' initialized | "
                f"Address: {self.address} | "
                f"Mode: {self.strategy_config['copy_mode']}"
            )

            return clob_client

        except Exception as e:
            log.error(f"Failed to initialize ClobClient: {e}")
            raise

    def run(self, target_wallet: str):
        """
        Start copy trading by subscribing to target wallet.

        Args:
            target_wallet: Target wallet address
        """
        log.info(f"CopyTrader '{self.name}' started following wallet: {target_wallet}")

        # Create callback function with target wallet parameter
        callback = partial(self._process_activities, target_wallet=target_wallet)

        # Subscribe to activity queue
        self.activity_queue.subscribe(target_wallet, callback)

        log.info(f"CopyTrader '{self.name}' subscribed to wallet {target_wallet} activities")

    def _process_activities(self, activities: List[Any], target_wallet: str):
        """
        Process a batch of activities.

        Args:
            activities: List of activity data
            target_wallet: Target wallet address
        """
        self.stats['total_activities'] += len(activities)
        log.info(f"[{self.name}] Received {len(activities)} activity(ies) from wallet {target_wallet}")

        for activity in activities:
            try:
                if self._should_process_activity(activity):
                    self._process_single_activity(activity, target_wallet)
                else:
                    self.stats['filtered_out'] += 1
            except Exception as e:
                log.error(f"[{self.name}] Unexpected error processing activity: {e}", exc_info=True)

    def _should_process_activity(self, activity: Any) -> bool:
        """
        Determine if activity should be processed (contains all filtering logic).

        Args:
            activity: Activity object

        Returns:
            True if should process, False to skip
        """
        # Filter 1: Only process TRADE type
        activity_type = getattr(activity, 'type', None)
        if activity_type != 'TRADE':
            log.debug(f"[{self.name}] Skipping non-trade activity: {activity_type}")
            return False

        # Filter 2: Check if target trade amount meets trigger threshold
        cash_amount = get_trade_value(activity)

        min_trigger = self.strategy_config.get('min_trigger_amount', 0)
        if cash_amount < min_trigger:
            log.info(
                f"[{self.name}] Skipping trade: target amount ${cash_amount:.2f} "
                f"below trigger threshold ${min_trigger:.2f}"
            )
            return False

        # Can add more filter conditions here:
        # - Maximum amount limit
        # - Market whitelist/blacklist
        # - Daily trade count/amount limits
        # etc...

        return True

    def _process_single_activity(self, activity: Any, target_wallet: str):
        """
        Process a single trading activity.

        Args:
            activity: Activity object
            target_wallet: Target wallet address
        """
        try:
            # Extract activity information
            condition_id = getattr(activity, 'condition_id', None)
            outcome = getattr(activity, 'outcome', None)
            side = getattr(activity, 'side', None)
            target_price = getattr(activity, 'price', None)
            market_title = getattr(activity, 'title', 'N/A')

            if not all([condition_id, outcome, side]):
                log.warning(f"[{self.name}] Incomplete activity data, skipping")
                return

            # Calculate trade size
            trade_size = self._calculate_trade_size(activity, target_wallet)

            log.info(
                f"[{self.name}] Preparing copy trade | "
                f"Market: {market_title} | "
                f"Side: {side} | "
                f"Outcome: {outcome} | "
                f"Amount: ${trade_size:.2f}"
            )

            # Execute trade (with retry)
            result = self._execute_trade_with_retry({
                'condition_id': condition_id,
                'outcome': outcome,
                'side': side,
                'size': trade_size,
                'price': target_price
            })

            if result:
                self.stats['trades_succeeded'] += 1
                log.info(f"[{self.name}] ✓ Copy trade successful | Order ID: {result.get('orderID', 'N/A')}")
            else:
                self.stats['trades_failed'] += 1

        except Exception as e:
            self.stats['trades_failed'] += 1
            log.error(f"[{self.name}] Failed to process single activity: {e}", exc_info=True)

    def _calculate_trade_size(self, activity: Any, target_wallet: str) -> float:
        """
        Calculate final trade amount (USDC) based on configured copy_mode.

        Args:
            activity: Activity object
            target_wallet: Target wallet address

        Returns:
            Calculated trade amount (USDC) with min/max limits applied
        """
        mode = self.strategy_config['copy_mode']
        target_value = get_trade_value(activity)

        if mode == 'scale':
            # Proportional scaling mode
            percentage = self.strategy_config['scale_percentage']
            calculated_size = target_value * (percentage / 100)
            log.debug(
                f"[{self.name}] Scale mode: "
                f"target amount ${target_value:.2f} × {percentage}% = ${calculated_size:.2f}"
            )

        elif mode == 'allocate':
            # Proportional allocation mode (not fully implemented yet)
            # TODO: Implement target wallet balance retrieval
            log.warning(f"[{self.name}] Allocate mode not fully implemented, falling back to Scale mode 10%")
            calculated_size = target_value * 0.1

        else:
            raise ValueError(f"Unsupported copy mode: {mode}")

        # Apply minimum amount limit
        min_amount = self.strategy_config.get('min_trade_amount', 0)
        if min_amount > 0 and calculated_size < min_amount:
            log.info(
                f"[{self.name}] Applying minimum amount limit: "
                f"${calculated_size:.2f} → ${min_amount:.2f}"
            )
            calculated_size = min_amount

        # Apply maximum amount limit
        max_amount = self.strategy_config.get('max_trade_amount', 0)
        if max_amount > 0 and calculated_size > max_amount:
            log.info(
                f"[{self.name}] Applying maximum amount limit: "
                f"${calculated_size:.2f} → ${max_amount:.2f}"
            )
            calculated_size = max_amount

        return calculated_size

    def _execute_trade_with_retry(
        self,
        params: Dict[str, Any],
        max_retries: int = 3
    ) -> Optional[Dict]:
        """
        Execute trade with retry on failure.

        Args:
            params: Trade parameter dictionary
            max_retries: Maximum retry attempts

        Returns:
            Order result dictionary, or None on failure
        """
        self.stats['trades_attempted'] += 1

        for attempt in range(max_retries):
            try:
                result = self._execute_trade(params)
                return result

            except InsufficientBalanceError as e:
                log.error(f"[{self.name}] Insufficient balance, skipping trade: {e}")
                return None

            except NetworkError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    log.warning(
                        f"[{self.name}] Network error, retrying in {wait_time}s "
                        f"({attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(wait_time)
                else:
                    log.error(f"[{self.name}] Trade failed, max retries reached: {e}")
                    return None

            except OrderExecutionError as e:
                log.error(f"[{self.name}] Order execution error: {e}")
                return None

            except Exception as e:
                log.error(f"[{self.name}] Trade execution exception: {e}", exc_info=True)
                return None

        return None

    def _execute_trade(self, params: Dict[str, Any]) -> Dict:
        """
        Prepare parameters and execute trade using clob_client based on configured order_type.

        Args:
            params: Trade parameters
                - condition_id: Market condition ID
                - outcome: Outcome (YES/NO)
                - side: Trade side (BUY/SELL)
                - size: Trade amount (USDC)
                - price: Price (optional, for limit orders)

        Returns:
            Order response dictionary

        Raises:
            InsufficientBalanceError: Insufficient balance
            NetworkError: Network error
            OrderExecutionError: Order execution error
        """
        try:
            condition_id = params['condition_id']
            outcome = params['outcome']
            side = params['side']
            amount = params['size']
            price = params.get('price')

            order_type = self.strategy_config.get('order_type', 'market')

            # Execute order using OrderExecutor
            return self.order_executor.execute_order(
                condition_id=condition_id,
                outcome=outcome,
                side=side,
                amount=amount,
                price=price,
                order_type=order_type
            )

        except KeyError as e:
            raise OrderExecutionError(f"Missing required parameter: {e}")
        except OrderExecutionError:
            raise
        except Exception as e:
            # Classify error type
            error_msg = str(e).lower()
            if 'balance' in error_msg or 'insufficient' in error_msg:
                raise InsufficientBalanceError(str(e))
            elif 'network' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
                raise NetworkError(str(e))
            else:
                raise OrderExecutionError(str(e))

    def get_stats(self) -> Dict[str, int]:
        """
        Get trading statistics.

        Returns:
            Statistics dictionary
        """
        return self.stats.copy()

    def print_stats(self):
        """Print trading statistics."""
        log.info(f"[{self.name}] Trading statistics:")
        log.info(f"  - Total activities: {self.stats['total_activities']}")
        log.info(f"  - Filtered out: {self.stats['filtered_out']}")
        log.info(f"  - Trades attempted: {self.stats['trades_attempted']}")
        log.info(f"  - Successful: {self.stats['trades_succeeded']}")
        log.info(f"  - Failed: {self.stats['trades_failed']}")

    def _log_balance(self):
        """Query and print current wallet balance."""
        try:
            # Query USDC balance and allowance
            # Note: asset_type="COLLATERAL" is used for USDC
            params = BalanceAllowanceParams(
                asset_type="COLLATERAL",
                signature_type=self.signature_type
            )
            result = self.clob_client.get_balance_allowance(params)

            # Extract balance info (USDC uses 6 decimal places)
            balance_raw = result.get('balance', 'N/A')
            allowance_raw = result.get('allowance', 'N/A')

            # Convert to actual USDC amount (divide by 10^6)
            balance_str = f"{float(balance_raw) / 1_000_000:.2f}" if balance_raw != 'N/A' else 'N/A'
            allowance_str = f"{float(allowance_raw) / 1_000_000:.2f}" if allowance_raw != 'N/A' else 'N/A'

            log.info(
                f"[{self.name}] Current USDC balance: {balance_str} | "
                f"Allowance: {allowance_str}"
            )

        except Exception as e:
            log.warning(f"[{self.name}] Failed to query balance: {e}")

    def _ensure_api_allowance(self):
        """
        Check and sync proxy mode API allowance.

        Proxy mode (signature_type=2) allowance management explanation:
        1. On-chain approval: Must be completed through Polymarket website (click "Enable Trading")
        2. API sync: Call update_balance_allowance() to let CLOB API know about on-chain approval status

        Important notes:
        - First-time use requires clicking "Enable Trading" on Polymarket website
        - This authorizes the proxy contract to approve USDC and Conditional Tokens for exchange contracts
        - This method only syncs API status, does not perform on-chain approval
        - If API is unavailable, will skip check and continue running (on-chain approval is independent)
        """
        try:
            log.info(f"[{self.name}] Checking proxy wallet allowance status...")

            # Query current API allowance status
            params = BalanceAllowanceParams(
                asset_type="COLLATERAL",
                signature_type=self.signature_type
            )
            result = self.clob_client.get_balance_allowance(params)

            # Extract current allowance (USDC uses 6 decimal places)
            current_allowance_raw = result.get('allowance', 0)
            current_allowance = float(current_allowance_raw) / 1_000_000

            # Extract balance info
            balance_raw = result.get('balance', 0)
            balance = float(balance_raw) / 1_000_000

            log.info(
                f"[{self.name}] Current status | "
                f"Balance: ${balance:.2f} | "
                f"Allowance: ${current_allowance:.2f}"
            )

            # Check if allowance is sufficient (at least equals balance, or large enough)
            if current_allowance > 0 and current_allowance >= balance * 0.9:
                log.info(f"[{self.name}] Allowance status normal, ready to trade")
                return

            # Allowance insufficient but not 0, try to sync
            if current_allowance > 0:
                log.info(f"[{self.name}] Allowance low, trying to sync API status...")
                try:
                    self.clob_client.update_balance_allowance(params)

                    # Query again to confirm
                    result_after = self.clob_client.get_balance_allowance(params)
                    new_allowance_raw = result_after.get('allowance', 0)
                    new_allowance = float(new_allowance_raw) / 1_000_000

                    log.info(f"[{self.name}] After sync Allowance: ${new_allowance:.2f}")

                    if new_allowance >= balance * 0.9:
                        log.info(f"[{self.name}] Allowance status updated, ready to trade")
                    else:
                        log.warning(
                            f"[{self.name}] Allowance still low, if trade fails, "
                            f"please 'Enable Trading' on Polymarket website"
                        )
                except Exception as sync_error:
                    log.warning(f"[{self.name}] Failed to sync allowance: {sync_error}")

                return

            # Allowance is 0 - this is a warning but not fatal
            log.warning(
                f"[{self.name}] API shows allowance is 0!\n"
                f"If on-chain approval completed (Enable Trading), this may just be an API sync issue.\n"
                f"Program will continue running, if trade fails, please check:\n"
                f"1. Clicked 'Enable Trading' on Polymarket website\n"
                f"2. Connected wallet address is: {self.proxy_address} (Proxy)\n"
                f"3. Wait a few minutes for API to sync on-chain status\n"
            )

            # Try to sync once
            try:
                log.info(f"[{self.name}] Trying to sync API allowance...")
                self.clob_client.update_balance_allowance(params)
                log.info(f"[{self.name}] API allowance sync request sent")
            except Exception as sync_error:
                log.warning(f"[{self.name}] Sync request failed: {sync_error}")

            # Don't raise exception, allow program to continue
            log.info(f"[{self.name}] Continuing initialization, will verify allowance on actual trade")

        except Exception as e:
            # Catch all exceptions, log but don't interrupt program
            log.warning(
                f"[{self.name}] Cannot check API allowance (possibly network issue): {e}\n"
                f"If you've completed 'Enable Trading' on Polymarket website,\n"
                f"program will continue running. On-chain approval is independent of API status."
            )
            log.info(f"[{self.name}] Continuing initialization...")
