"""
复制交易核心模块

提供自动化的复制交易功能，监听目标钱包活动并根据配置策略执行交易。
"""

import os
import time
import warnings
from functools import partial
from typing import List, Optional, Dict, Any

import requests
from web3 import Web3
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType, BalanceAllowanceParams, \
    PartialCreateOrderOptions

from src.activity_queue import ActivityQueue
from src.config_loader import load_private_key
from src.logger import log

# Suppress SSL verification warnings when using corporate proxy
warnings.filterwarnings('ignore', message='Unverified HTTPS request')
# Also suppress urllib3 warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================== 合约地址和配置 ====================
# Polygon 网络配置
POLYGON_RPC_URL = "https://polygon-rpc.com"
CHAIN_ID = 137

# 代币合约地址
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CONDITIONAL_TOKENS_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# 交易所合约地址（需要授权的三个合约）
EXCHANGE_ADDRESSES = [
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
]

# ERC20 ABI (只需要 approve 和 allowance 方法)
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

# ERC1155 ABI (只需要 setApprovalForAll 和 isApprovedForAll 方法)
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

# 无限授权额度
INFINITE_ALLOWANCE = 2**256 - 1


class CopyTraderError(Exception):
    """复制交易基础异常类"""
    pass


class InsufficientBalanceError(CopyTraderError):
    """余额不足异常"""
    pass


class NetworkError(CopyTraderError):
    """网络错误异常"""
    pass


class OrderExecutionError(CopyTraderError):
    """订单执行错误异常"""
    pass


class CopyTrader:
    """
    复制交易核心类

    功能：
    1. 从 ActivityQueue 订阅目标钱包的交易活动
    2. 根据配置的策略过滤和计算交易规模
    3. 调用 py-clob-client 执行交易
    4. 提供错误处理和重试机制
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
        初始化复制交易器

        Args:
            wallet_config: 用户钱包配置（包含地址、私钥来源、策略等）
            activity_queue: 活动队列实例
            chain_id: 区块链ID，默认 137 (Polygon mainnet)
            host: CLOB API 主机地址
            polygon_rpc_config: Polygon RPC 配置（包含 url 和 proxy）
        """
        self.name = wallet_config['name']
        self.address = wallet_config['address']
        self.strategy_config = wallet_config['copy_strategy']
        self.activity_queue = activity_queue

        # 获取签名类型和代理地址配置
        self.signature_type = wallet_config.get('signature_type', 0)  # 默认使用 EOA 模式
        self.proxy_address = wallet_config.get('proxy_address')  # 代理合约地址（funder）

        # 安全加载私钥
        private_key = load_private_key(wallet_config)
        self.private_key = private_key  # 保存以便后续使用

        # 初始化 Web3 客户端（用于代币授权）
        try:
            # 从配置获取 RPC URL 和代理设置
            rpc_url = POLYGON_RPC_URL
            proxy = None
            verify_ssl = True  # 默认验证 SSL

            if polygon_rpc_config:
                rpc_url = polygon_rpc_config.get('url', POLYGON_RPC_URL)
                proxy = polygon_rpc_config.get('proxy')
                verify_ssl = polygon_rpc_config.get('verify_ssl', True)
                # 也可以从环境变量读取代理
                if not proxy:
                    proxy = os.environ.get('POLYGON_RPC_PROXY')
            else:
                # 尝试从环境变量读取代理
                proxy = os.environ.get('POLYGON_RPC_PROXY')

            # 也可以从环境变量读取 SSL 验证设置
            if os.environ.get('POLYGON_RPC_VERIFY_SSL', '').lower() in ('false', '0'):
                verify_ssl = False
            elif os.environ.get('POLYGON_RPC_VERIFY_SSL', '').lower() in ('true', '1'):
                verify_ssl = True

            # 创建自定义 Session 对象
            session = requests.Session()
            session.verify = verify_ssl

            # 配置 HTTPProvider 的请求参数
            request_kwargs = {'timeout': 60 if proxy else 30}

            if proxy:
                session.proxies = {
                    'http': proxy,
                    'https': proxy
                }
                log.info(f"[{self.name}] Using proxy for Polygon RPC: {proxy} (SSL verify: {verify_ssl})")

            # 创建 Web3 实例，传入自定义 session
            provider = Web3.HTTPProvider(rpc_url, request_kwargs=request_kwargs, session=session)
            self.w3 = Web3(provider)

            if not self.w3.is_connected():
                log.warning(f"[{self.name}] 无法连接到 Polygon 网络，代币授权功能可能不可用")
        except Exception as e:
            log.warning(f"[{self.name}] 初始化 Web3 客户端失败: {e}")
            self.w3 = None

        # 检查并设置代币授权
        # 注意：代理模式（signature_type=2）不需要手动设置链上授权
        try:
            if self.signature_type == 0:
                # EOA 模式：需要手动设置链上代币授权
                self._ensure_token_approvals()
            else:
                log.info(f"[{self.name}] 代理模式跳过链上代币授权（由 Polymarket 管理）")
        except Exception as e:
            log.warning(f"[{self.name}] 代币授权失败: {e}")

        # 初始化 CLOB 客户端
        try:
            # 根据配置的 signature_type 初始化客户端
            # signature_type=0: 标准 EOA 签名，直接使用私钥
            # signature_type=2: 浏览器钱包代理模式，使用 Polymarket 代理合约
            client_params = {
                'host': host,
                'key': private_key,
                'chain_id': chain_id,
                'signature_type': self.signature_type,
            }

            # 如果是代理模式，需要指定 funder 地址
            if self.signature_type == 2:
                if not self.proxy_address:
                    raise ValueError(
                        f"钱包 '{self.name}' 使用 signature_type=2（代理模式），"
                        f"必须配置 proxy_address（代理合约地址）"
                    )
                client_params['funder'] = self.proxy_address
                log.info(
                    f"[{self.name}] 使用代理模式 | "
                    f"EOA: {self.address} | "
                    f"Funder: {self.proxy_address}"
                )
            else:
                log.info(f"[{self.name}] 使用 EOA 直接签名模式")

            self.clob_client = ClobClient(**client_params)

            # 创建或派生 API credentials (Level 2 认证所需)
            try:
                creds = self.clob_client.create_or_derive_api_creds()
                self.clob_client.set_api_creds(creds)
                log.info(f"CopyTrader '{self.name}' API credentials 已设置")
            except Exception as e:
                log.warning(f"设置 API credentials 失败: {e}，部分功能可能不可用")

            log.info(
                f"CopyTrader '{self.name}' 已初始化 | "
                f"地址: {self.address} | "
                f"模式: {self.strategy_config['copy_mode']}"
            )

            # 查询并打印余额
            self._log_balance()

            # 对于代理模式，设置 API allowance
            if self.signature_type == 2:
                self._ensure_api_allowance()

        except Exception as e:
            log.error(f"初始化 ClobClient 失败: {e}")
            raise

        # 交易统计
        self.stats = {
            'total_activities': 0,
            'filtered_out': 0,
            'trades_attempted': 0,
            'trades_succeeded': 0,
            'trades_failed': 0
        }

    def run(self, target_wallet: str):
        """
        启动复制交易，订阅目标钱包

        Args:
            target_wallet: 目标钱包地址
        """
        log.info(f"CopyTrader '{self.name}' 开始跟随钱包: {target_wallet}")

        # 创建带目标钱包参数的回调函数
        callback = partial(self._process_activities, target_wallet=target_wallet)

        # 订阅活动队列
        self.activity_queue.subscribe(target_wallet, callback)

        log.info(f"CopyTrader '{self.name}' 已订阅钱包 {target_wallet} 的活动")

    def _process_activities(self, activities: List[Any], target_wallet: str):
        """
        处理一批活动

        Args:
            activities: 活动数据列表
            target_wallet: 目标钱包地址
        """
        self.stats['total_activities'] += len(activities)
        log.info(f"[{self.name}] 收到 {len(activities)} 条活动来自钱包 {target_wallet}")

        for activity in activities:
            try:
                if self._should_process_activity(activity):
                    self._process_single_activity(activity, target_wallet)
                else:
                    self.stats['filtered_out'] += 1
            except Exception as e:
                log.error(f"[{self.name}] 处理活动时发生未预期错误: {e}", exc_info=True)

    def _should_process_activity(self, activity: Any) -> bool:
        """
        判断是否应该处理该活动（包含所有过滤逻辑）

        Args:
            activity: 活动对象

        Returns:
            True 表示应该处理，False 表示跳过
        """
        # 过滤1: 只处理 TRADE 类型
        activity_type = getattr(activity, 'type', None)
        if activity_type != 'TRADE':
            log.debug(f"[{self.name}] 跳过非交易活动: {activity_type}")
            return False

        # 过滤2: 检查目标交易金额是否达到触发阈值
        cash_amount = self._get_trade_value(activity)

        min_trigger = self.strategy_config.get('min_trigger_amount', 0)
        if cash_amount < min_trigger:
            log.info(
                f"[{self.name}] 跳过交易: 目标金额 ${cash_amount:.2f} "
                f"低于触发阈值 ${min_trigger:.2f}"
            )
            return False

        # 可以在这里添加更多过滤条件：
        # - 最大金额限制
        # - 市场黑白名单
        # - 每日交易次数/金额限制
        # 等等...

        return True

    def _process_single_activity(self, activity: Any, target_wallet: str):
        """
        处理单个交易活动

        Args:
            activity: 活动对象
            target_wallet: 目标钱包地址
        """
        try:
            # 提取活动信息
            condition_id = getattr(activity, 'condition_id', None)
            outcome = getattr(activity, 'outcome', None)
            side = getattr(activity, 'side', None)
            target_price = getattr(activity, 'price', None)
            market_title = getattr(activity, 'title', 'N/A')

            if not all([condition_id, outcome, side]):
                log.warning(f"[{self.name}] 活动数据不完整，跳过")
                return

            # 计算交易规模
            trade_size = self._calculate_trade_size(activity, target_wallet)

            log.info(
                f"[{self.name}] 准备复制交易 | "
                f"市场: {market_title} | "
                f"方向: {side} | "
                f"结果: {outcome} | "
                f"金额: ${trade_size:.2f}"
            )

            # 执行交易（带重试）
            result = self._execute_trade_with_retry({
                'condition_id': condition_id,
                'outcome': outcome,
                'side': side,
                'size': trade_size,
                'price': target_price
            })

            if result:
                self.stats['trades_succeeded'] += 1
                log.info(f"[{self.name}] ✓ 复制交易成功 | 订单ID: {result.get('orderID', 'N/A')}")
            else:
                self.stats['trades_failed'] += 1

        except Exception as e:
            self.stats['trades_failed'] += 1
            log.error(f"[{self.name}] 处理单个活动失败: {e}", exc_info=True)

    def _get_trade_value(self, activity: Any) -> float:
        """
        获取交易的 USDC 价值

        Args:
            activity: 活动对象

        Returns:
            交易价值（USDC）
        """
        cash_amount = getattr(activity, 'cash_amount', 0)
        if cash_amount > 0:
            return float(cash_amount)

        # 如果 cash_amount 为 0，用 size × price 计算
        size = float(getattr(activity, 'size', 0))
        price = float(getattr(activity, 'price', 0))
        return size * price

    def _calculate_trade_size(self, activity: Any, target_wallet: str) -> float:
        """
        根据配置的 copy_mode 计算最终的交易金额 (USDC)

        Args:
            activity: 活动对象
            target_wallet: 目标钱包地址

        Returns:
            计算后的交易金额（USDC），已应用最小和最大金额限制
        """
        mode = self.strategy_config['copy_mode']
        target_value = self._get_trade_value(activity)

        if mode == 'scale':
            # 按比例缩放模式
            percentage = self.strategy_config['scale_percentage']
            calculated_size = target_value * (percentage / 100)
            log.debug(
                f"[{self.name}] Scale 模式: "
                f"目标金额 ${target_value:.2f} × {percentage}% = ${calculated_size:.2f}"
            )

        elif mode == 'allocate':
            # 按比例分配模式（暂未实现获取目标钱包余额的功能）
            # TODO: 实现获取目标钱包余额
            log.warning(f"[{self.name}] Allocate 模式暂未完全实现，降级为 Scale 模式 10%")
            calculated_size = target_value * 0.1

        else:
            raise ValueError(f"不支持的复制模式: {mode}")

        # 应用最小金额限制
        min_amount = self.strategy_config.get('min_trade_amount', 0)
        if min_amount > 0 and calculated_size < min_amount:
            log.info(
                f"[{self.name}] 应用最小金额限制: "
                f"${calculated_size:.2f} → ${min_amount:.2f}"
            )
            calculated_size = min_amount

        # 应用最大金额限制
        max_amount = self.strategy_config.get('max_trade_amount', 0)
        if max_amount > 0 and calculated_size > max_amount:
            log.info(
                f"[{self.name}] 应用最大金额限制: "
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
        执行交易并在失败时重试

        Args:
            params: 交易参数字典
            max_retries: 最大重试次数

        Returns:
            订单结果字典，失败返回 None
        """
        self.stats['trades_attempted'] += 1

        for attempt in range(max_retries):
            try:
                result = self._execute_trade(params)
                return result

            except InsufficientBalanceError as e:
                log.error(f"[{self.name}] 余额不足，跳过交易: {e}")
                return None

            except NetworkError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避: 1s, 2s, 4s
                    log.warning(
                        f"[{self.name}] 网络错误，{wait_time}秒后重试 "
                        f"({attempt + 1}/{max_retries}): {e}"
                    )
                    time.sleep(wait_time)
                else:
                    log.error(f"[{self.name}] 交易失败，已达最大重试次数: {e}")
                    return None

            except OrderExecutionError as e:
                log.error(f"[{self.name}] 订单执行错误: {e}")
                return None

            except Exception as e:
                log.error(f"[{self.name}] 交易执行异常: {e}", exc_info=True)
                return None

        return None

    def _execute_trade(self, params: Dict[str, Any]) -> Dict:
        """
        根据配置的 order_type 准备参数并调用 clob_client 执行交易

        Args:
            params: 交易参数
                - condition_id: 市场条件ID
                - outcome: 结果（YES/NO）
                - side: 交易方向（BUY/SELL）
                - size: 交易金额（USDC）
                - price: 价格（可选，用于限价单）

        Returns:
            订单响应字典

        Raises:
            InsufficientBalanceError: 余额不足
            NetworkError: 网络错误
            OrderExecutionError: 订单执行错误
        """
        try:
            condition_id = params['condition_id']
            outcome = params['outcome']
            side_str = params['side']
            amount = params['size']
            price = params.get('price')

            # 标准化 side 字符串（BUY 或 SELL）
            side = side_str.upper()

            # 获取 token_id
            token_id = self._get_token_id(condition_id, outcome)
            if not token_id:
                raise OrderExecutionError(
                    f"无法获取 token_id: condition_id={condition_id}, outcome={outcome}"
                )

            order_type = self.strategy_config.get('order_type', 'market')

            if order_type == 'market':
                # 市价单
                return self._execute_market_order(token_id, side, amount)
            elif order_type == 'limit':
                # 限价单
                if not price:
                    raise OrderExecutionError("限价单需要指定价格")
                return self._execute_limit_order(token_id, side, amount, price)
            else:
                raise OrderExecutionError(f"不支持的订单类型: {order_type}")

        except KeyError as e:
            raise OrderExecutionError(f"缺少必需参数: {e}")
        except Exception as e:
            # 判断错误类型
            error_msg = str(e).lower()
            if 'balance' in error_msg or 'insufficient' in error_msg:
                raise InsufficientBalanceError(str(e))
            elif 'network' in error_msg or 'timeout' in error_msg or 'connection' in error_msg:
                raise NetworkError(str(e))
            else:
                raise OrderExecutionError(str(e))

    def _get_token_id(self, condition_id: str, outcome: str) -> Optional[str]:
        """
        从 condition_id 和 outcome 获取 token_id

        Args:
            condition_id: 市场条件ID
            outcome: 结果（YES/NO）

        Returns:
            token_id 字符串，失败返回 None
        """
        try:
            market_info = self.clob_client.get_market(condition_id)

            # 从市场信息中查找对应 outcome 的 token_id
            # 市场信息结构可能类似: {'tokens': [{'outcome': 'YES', 'token_id': '...'}, ...]}
            if 'tokens' in market_info:
                for token in market_info['tokens']:
                    if token.get('outcome', '').upper() == outcome.upper():
                        return token.get('token_id')

            log.error(f"[{self.name}] 在市场信息中未找到 outcome '{outcome}' 对应的 token_id")
            return None

        except Exception as e:
            log.error(f"[{self.name}] 获取 token_id 失败: {e}")
            return None

    def _execute_market_order(
        self,
        token_id: str,
        side: Any,
        amount: float
    ) -> Dict:
        """
        执行市价单

        Args:
            token_id: 代币ID
            side: 交易方向（BUY/SELL）
            amount: 交易金额（USDC）

        Returns:
            订单响应
        """
        try:
            # 创建市价单参数
            market_order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=side,
                order_type=OrderType.FOK  # Fill or Kill
            )

            # 创建签名订单
            signed_order = self.clob_client.create_market_order(market_order_args)

            # 提交订单
            response = self.clob_client.post_order(signed_order, OrderType.FOK)

            log.info(
                f"[{self.name}] 市价单已提交 | "
                f"token_id: {token_id} | "
                f"方向: {side} | "
                f"金额: ${amount:.2f}"
            )

            return response

        except Exception as e:
            log.error(f"[{self.name}] 市价单执行失败: {e}")
            raise

    def _execute_limit_order(
        self,
        token_id: str,
        side: Any,
        size: float,
        price: float
    ) -> Dict:
        """
        执行限价单

        Args:
            token_id: 代币ID
            side: 交易方向（BUY/SELL）
            size: 交易数量
            price: 限价

        Returns:
            订单响应
        """
        try:
            # 创建限价单参数
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=size,
                side=side
            )

            log.info(
                f"[{self.name}] 创建订单参数 | "
                f"token_id: {token_id} | "
                f"方向: {side} | "
                f"价格: {price} | "
                f"数量: {size} | "
                f"signature_type: {self.signature_type}"
            )

            # 创建签名订单
            signed_order = self.clob_client.create_order(order_args, PartialCreateOrderOptions(neg_risk=True))

            # 打印签名订单详情（用于调试）
            import json
            log.info(f"[{self.name}] 签名订单内容:")
            log.info(json.dumps(signed_order, indent=2, default=str))

            # 提交订单（注意：post_order 的第二个参数对限价单应该使用 OrderType.GTD）
            response = self.clob_client.post_order(signed_order)

            log.info(
                f"[{self.name}] 限价单已提交 | "
                f"token_id: {token_id} | "
                f"方向: {side} | "
                f"价格: {price} | "
                f"数量: {size}"
            )

            return response

        except Exception as e:
            log.error(f"[{self.name}] 限价单执行失败: {e}")
            raise

    def get_stats(self) -> Dict[str, int]:
        """
        获取交易统计信息

        Returns:
            统计信息字典
        """
        return self.stats.copy()

    def print_stats(self):
        """打印交易统计信息"""
        log.info(f"[{self.name}] 交易统计:")
        log.info(f"  - 总活动数: {self.stats['total_activities']}")
        log.info(f"  - 已过滤: {self.stats['filtered_out']}")
        log.info(f"  - 尝试交易: {self.stats['trades_attempted']}")
        log.info(f"  - 成功: {self.stats['trades_succeeded']}")
        log.info(f"  - 失败: {self.stats['trades_failed']}")

    def _ensure_token_approvals(self):
        """
        检查并确保所有必要的代币授权已设置

        在第一次交易前需要授权：
        1. USDC (ERC20) 给三个交易所合约
        2. Conditional Tokens (ERC1155) 给三个交易所合约
        """
        if not self.w3 or not self.w3.is_connected():
            log.warning(f"[{self.name}] Web3 未连接，跳过代币授权检查")
            return

        log.info(f"[{self.name}] 正在检查代币授权状态...")

        try:
            # 检查并授权 USDC
            self._ensure_usdc_approvals()

            # 检查并授权 Conditional Tokens
            self._ensure_conditional_tokens_approvals()

            log.info(f"[{self.name}] ✓ 所有代币授权已就绪")

        except Exception as e:
            log.error(f"[{self.name}] 代币授权检查失败: {e}", exc_info=True)
            raise

    def _ensure_usdc_approvals(self):
        """
        检查并授权 USDC (ERC20) 给所有交易所合约
        """
        usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI
        )

        for exchange_address in EXCHANGE_ADDRESSES:
            try:
                checksum_exchange = Web3.to_checksum_address(exchange_address)

                # 检查当前授权额度
                current_allowance = usdc_contract.functions.allowance(
                    Web3.to_checksum_address(self.address),
                    checksum_exchange
                ).call()

                if current_allowance >= INFINITE_ALLOWANCE // 2:
                    log.debug(
                        f"[{self.name}] USDC 已授权给 {exchange_address[:10]}... "
                        f"(额度: {current_allowance})"
                    )
                    continue

                # 需要授权
                log.info(
                    f"[{self.name}] 正在授权 USDC 给交易所 {exchange_address[:10]}..."
                )

                # 构建授权交易
                approve_txn = usdc_contract.functions.approve(
                    checksum_exchange,
                    INFINITE_ALLOWANCE
                ).build_transaction({
                    'from': Web3.to_checksum_address(self.address),
                    'nonce': self.w3.eth.get_transaction_count(
                        Web3.to_checksum_address(self.address)
                    ),
                    'gas': 100000,
                    'gasPrice': self.w3.eth.gas_price,
                    'chainId': CHAIN_ID
                })

                # 签名交易
                signed_txn = self.w3.eth.account.sign_transaction(
                    approve_txn,
                    private_key=self.private_key
                )

                # 发送交易
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)

                log.info(
                    f"[{self.name}] USDC 授权交易已提交: {tx_hash.hex()}"
                )

                # 等待交易确认
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

                if receipt['status'] == 1:
                    log.info(
                        f"[{self.name}] ✓ USDC 授权成功: {exchange_address[:10]}..."
                    )
                else:
                    log.error(
                        f"[{self.name}] ✗ USDC 授权失败: {exchange_address[:10]}..."
                    )
                    raise OrderExecutionError(
                        f"USDC 授权交易失败: {tx_hash.hex()}"
                    )

            except Exception as e:
                log.error(
                    f"[{self.name}] 授权 USDC 给 {exchange_address} 时出错: {e}",
                    exc_info=True
                )
                raise

    def _ensure_conditional_tokens_approvals(self):
        """
        检查并授权 Conditional Tokens (ERC1155) 给所有交易所合约
        """
        ct_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(CONDITIONAL_TOKENS_ADDRESS),
            abi=ERC1155_ABI
        )

        for exchange_address in EXCHANGE_ADDRESSES:
            try:
                checksum_exchange = Web3.to_checksum_address(exchange_address)

                # 检查当前是否已授权
                is_approved = ct_contract.functions.isApprovedForAll(
                    Web3.to_checksum_address(self.address),
                    checksum_exchange
                ).call()

                if is_approved:
                    log.debug(
                        f"[{self.name}] Conditional Tokens 已授权给 {exchange_address[:10]}..."
                    )
                    continue

                # 需要授权
                log.info(
                    f"[{self.name}] 正在授权 Conditional Tokens 给交易所 {exchange_address[:10]}..."
                )

                # 构建授权交易
                approve_txn = ct_contract.functions.setApprovalForAll(
                    checksum_exchange,
                    True
                ).build_transaction({
                    'from': Web3.to_checksum_address(self.address),
                    'nonce': self.w3.eth.get_transaction_count(
                        Web3.to_checksum_address(self.address)
                    ),
                    'gas': 100000,
                    'gasPrice': self.w3.eth.gas_price,
                    'chainId': CHAIN_ID
                })

                # 签名交易
                signed_txn = self.w3.eth.account.sign_transaction(
                    approve_txn,
                    private_key=self.private_key
                )

                # 发送交易
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)

                log.info(
                    f"[{self.name}] Conditional Tokens 授权交易已提交: {tx_hash.hex()}"
                )

                # 等待交易确认
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

                if receipt['status'] == 1:
                    log.info(
                        f"[{self.name}] ✓ Conditional Tokens 授权成功: {exchange_address[:10]}..."
                    )
                else:
                    log.error(
                        f"[{self.name}] ✗ Conditional Tokens 授权失败: {exchange_address[:10]}..."
                    )
                    raise OrderExecutionError(
                        f"Conditional Tokens 授权交易失败: {tx_hash.hex()}"
                    )

            except Exception as e:
                log.error(
                    f"[{self.name}] 授权 Conditional Tokens 给 {exchange_address} 时出错: {e}",
                    exc_info=True
                )
                raise

    def _log_balance(self):
        """查询并打印当前钱包余额"""
        try:
            # 查询 USDC 余额和授权额度
            # 注意：asset_type="COLLATERAL" 用于查询 USDC
            params = BalanceAllowanceParams(
                asset_type="COLLATERAL",
                signature_type=self.signature_type  # 使用配置的签名类型
            )
            result = self.clob_client.get_balance_allowance(params)

            # 提取余额信息（USDC 使用 6 位小数精度）
            balance_raw = result.get('balance', 'N/A')
            allowance_raw = result.get('allowance', 'N/A')

            # 转换为实际 USDC 数量（除以 10^6）
            if balance_raw != 'N/A':
                balance = float(balance_raw) / 1_000_000
                balance_str = f"{balance:.2f}"
            else:
                balance_str = 'N/A'

            if allowance_raw != 'N/A':
                allowance = float(allowance_raw) / 1_000_000
                allowance_str = f"{allowance:.2f}"
            else:
                allowance_str = 'N/A'

            log.info(
                f"[{self.name}] 当前 USDC 余额: {balance_str} | "
                f"授权额度: {allowance_str}"
            )

        except Exception as e:
            log.warning(f"[{self.name}] 查询余额失败: {e}")

    def _ensure_api_allowance(self):
        """
        检查并同步代理模式的 API allowance

        代理模式（signature_type=2）的 allowance 管理说明：
        1. 链上授权：必须通过 Polymarket 网站界面完成（点击 "Enable Trading"）
        2. API 同步：调用 update_balance_allowance() 让 CLOB API 知晓链上授权状态

        重要提示：
        - 首次使用前，必须在 Polymarket 网站上点击 "Enable Trading"
        - 这会让代理合约授权 USDC 和 Conditional Tokens 给交易所合约
        - 本方法仅同步 API 状态，不执行链上授权
        - 如果 API 不可用，会跳过检查并继续运行（链上授权是独立的）
        """
        try:
            log.info(f"[{self.name}] 正在检查代理钱包 allowance 状态...")

            # 查询当前 API allowance 状态
            params = BalanceAllowanceParams(
                asset_type="COLLATERAL",
                signature_type=self.signature_type
            )
            result = self.clob_client.get_balance_allowance(params)

            # 提取当前 allowance（USDC 使用 6 位小数精度）
            current_allowance_raw = result.get('allowance', 0)
            current_allowance = float(current_allowance_raw) / 1_000_000

            # 提取余额信息
            balance_raw = result.get('balance', 0)
            balance = float(balance_raw) / 1_000_000

            log.info(
                f"[{self.name}] 当前状态 | "
                f"余额: ${balance:.2f} | "
                f"Allowance: ${current_allowance:.2f}"
            )

            # 检查 allowance 是否足够（至少等于余额，或者足够大）
            if current_allowance > 0 and current_allowance >= balance * 0.9:
                log.info(f"[{self.name}] Allowance 状态正常，可以开始交易")
                return

            # Allowance 不足但不为 0，尝试同步
            if current_allowance > 0:
                log.info(f"[{self.name}] Allowance 较低，尝试同步 API 状态...")
                try:
                    self.clob_client.update_balance_allowance(params)

                    # 再次查询确认
                    result_after = self.clob_client.get_balance_allowance(params)
                    new_allowance_raw = result_after.get('allowance', 0)
                    new_allowance = float(new_allowance_raw) / 1_000_000

                    log.info(f"[{self.name}] 同步后 Allowance: ${new_allowance:.2f}")

                    if new_allowance >= balance * 0.9:
                        log.info(f"[{self.name}] Allowance 状态已更新，可以交易")
                    else:
                        log.warning(
                            f"[{self.name}] Allowance 仍然较低，如遇到交易失败，"
                            f"请在 Polymarket 网站上重新 'Enable Trading'"
                        )
                except Exception as sync_error:
                    log.warning(f"[{self.name}] 同步 allowance 失败: {sync_error}")

                return

            # Allowance 为 0 - 这是个警告，但不致命
            log.warning(
                f"[{self.name}] API 显示 allowance 为 0！\n"
                f"如果链上已经完成授权（Enable Trading），这可能只是 API 同步问题。\n"
                f"程序将继续运行，如果交易失败，请检查：\n"
                f"1. 已在 Polymarket 网站上点击 'Enable Trading'\n"
                f"2. 连接的钱包地址是：{self.proxy_address} (Proxy)\n"
                f"3. 等待几分钟让 API 同步链上状态\n"
            )

            # 尝试同步一次
            try:
                log.info(f"[{self.name}] 尝试同步 API allowance...")
                self.clob_client.update_balance_allowance(params)
                log.info(f"[{self.name}] API allowance 同步请求已发送")
            except Exception as sync_error:
                log.warning(f"[{self.name}] 同步请求失败: {sync_error}")

            # 不抛出异常，允许程序继续运行
            log.info(f"[{self.name}] 继续初始化，将在实际交易时验证 allowance")

        except Exception as e:
            # 捕获所有异常，记录日志但不中断程序
            log.warning(
                f"[{self.name}] 无法检查 API allowance（可能是网络问题）: {e}\n"
                f"如果您已在 Polymarket 网站上完成 'Enable Trading'，\n"
                f"程序将继续运行。链上授权与 API 状态是独立的。"
            )
            log.info(f"[{self.name}] 继续初始化...")
