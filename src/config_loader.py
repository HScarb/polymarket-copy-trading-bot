import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_config(path: str = "config.yaml") -> dict:
    """从指定路径加载 YAML 配置文件并返回一个字典"""
    # 首先加载 .env 文件（如果存在）
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env file: {env_path}")
    else:
        print(f"Note: .env file not found, will use system environment variables")

    config_path = Path(path)

    # 如果路径不是绝对路径,尝试从项目根目录查找
    if not config_path.is_absolute():
        config_path = root_dir / path

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"配置文件为空或格式错误: {path}")

    # 验证并处理用户钱包配置
    if 'user_wallets' in config:
        config['user_wallets'] = _validate_user_wallets(config['user_wallets'])

    return config


def _validate_user_wallets(wallets: list) -> list:
    """
    验证用户钱包配置的完整性和正确性

    Args:
        wallets: 用户钱包配置列表

    Returns:
        验证后的钱包配置列表

    Raises:
        ValueError: 配置验证失败
    """
    if not wallets:
        return []

    validated = []

    for idx, wallet in enumerate(wallets):
        if not isinstance(wallet, dict):
            raise ValueError(f"用户钱包配置 #{idx} 必须是字典类型")

        # 验证必需字段
        required_fields = ['name', 'address']
        for field in required_fields:
            if field not in wallet:
                raise ValueError(f"用户钱包配置 '{wallet.get('name', f'#{idx}')}' 缺少必需字段: {field}")

        # 验证私钥配置（必须有 private_key_env）
        if 'private_key_env' not in wallet:
            raise ValueError(
                f"用户钱包 '{wallet['name']}' 必须指定 'private_key_env' 字段以安全地加载私钥"
            )

        # 验证复制策略配置
        if 'copy_strategy' not in wallet:
            raise ValueError(f"用户钱包 '{wallet['name']}' 缺少 'copy_strategy' 配置")

        strategy = wallet['copy_strategy']

        # 验证复制模式
        copy_mode = strategy.get('copy_mode')
        if copy_mode not in ['scale', 'allocate']:
            raise ValueError(
                f"用户钱包 '{wallet['name']}' 的 copy_mode 必须是 'scale' 或 'allocate'，当前值: {copy_mode}"
            )

        # 如果是 scale 模式，必须有 scale_percentage
        if copy_mode == 'scale' and 'scale_percentage' not in strategy:
            raise ValueError(
                f"用户钱包 '{wallet['name']}' 使用 scale 模式，必须指定 'scale_percentage'"
            )

        # 验证订单类型
        order_type = strategy.get('order_type', 'market')
        if order_type not in ['market', 'limit']:
            raise ValueError(
                f"用户钱包 '{wallet['name']}' 的 order_type 必须是 'market' 或 'limit'，当前值: {order_type}"
            )

        # 验证 signature_type 和代理配置
        signature_type = wallet.get('signature_type', 0)
        if signature_type not in [0, 1, 2]:
            raise ValueError(
                f"用户钱包 '{wallet['name']}' 的 signature_type 必须是 0, 1 或 2，当前值: {signature_type}"
            )

        # 如果使用代理模式（signature_type=2），必须配置 proxy_address
        if signature_type == 2:
            if 'proxy_address' not in wallet or not wallet['proxy_address']:
                raise ValueError(
                    f"用户钱包 '{wallet['name']}' 使用 signature_type=2（代理模式），"
                    f"必须配置 'proxy_address'（Polymarket 代理合约地址）"
                )

        # 设置默认值
        wallet.setdefault('signature_type', 0)  # 默认使用 EOA 模式
        strategy.setdefault('min_trigger_amount', 0)
        strategy.setdefault('max_trade_amount', 0)  # 0 表示不限制
        strategy.setdefault('order_type', 'market')
        strategy.setdefault('limit_order_duration', 7200)

        validated.append(wallet)

    return validated


def load_private_key(wallet_config: dict) -> str:
    """
    安全地加载用户钱包的私钥

    Args:
        wallet_config: 钱包配置字典

    Returns:
        私钥字符串

    Raises:
        ValueError: 私钥加载失败
    """
    if 'private_key_env' in wallet_config:
        env_var = wallet_config['private_key_env']
        key = os.environ.get(env_var)
        if not key:
            raise ValueError(
                f"环境变量 '{env_var}' 未设置，无法加载钱包 '{wallet_config['name']}' 的私钥"
            )
        return key
    else:
        raise ValueError(
            f"钱包 '{wallet_config['name']}' 必须指定 'private_key_env' 字段"
        )
