"""Configuration loading utilities."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_config(path: str = "config.yaml") -> dict:
    """
    Load YAML configuration file from specified path and return as dictionary.

    Args:
        path: Configuration file path

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration file is empty or invalid
    """
    # First load .env file (if it exists)
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env file: {env_path}")
    else:
        print(f"Note: .env file not found, will use system environment variables")

    config_path = Path(path)

    # If path is not absolute, try to find from project root
    if not config_path.is_absolute():
        config_path = root_dir / path

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if not config:
        raise ValueError(f"Configuration file is empty or has invalid format: {path}")

    # Validate and process user wallet configuration
    if 'user_wallets' in config:
        config['user_wallets'] = _validate_user_wallets(config['user_wallets'])

    return config


def _validate_user_wallets(wallets: list) -> list:
    """
    Validate user wallet configuration completeness and correctness.

    Args:
        wallets: User wallet configuration list

    Returns:
        Validated wallet configuration list

    Raises:
        ValueError: Configuration validation failed
    """
    if not wallets:
        return []

    validated = []

    for idx, wallet in enumerate(wallets):
        if not isinstance(wallet, dict):
            raise ValueError(f"User wallet config #{idx} must be a dictionary")

        # Validate required fields
        required_fields = ['name', 'address']
        for field in required_fields:
            if field not in wallet:
                raise ValueError(f"User wallet config '{wallet.get('name', f'#{idx}')}' missing required field: {field}")

        # Validate private key configuration (must have private_key_env)
        if 'private_key_env' not in wallet:
            raise ValueError(
                f"User wallet '{wallet['name']}' must specify 'private_key_env' field to securely load private key"
            )

        # Validate copy strategy configuration
        if 'copy_strategy' not in wallet:
            raise ValueError(f"User wallet '{wallet['name']}' missing 'copy_strategy' configuration")

        strategy = wallet['copy_strategy']

        # Validate copy mode
        copy_mode = strategy.get('copy_mode')
        if copy_mode not in ['scale', 'allocate']:
            raise ValueError(
                f"User wallet '{wallet['name']}' copy_mode must be 'scale' or 'allocate', current value: {copy_mode}"
            )

        # If scale mode, must have scale_percentage
        if copy_mode == 'scale' and 'scale_percentage' not in strategy:
            raise ValueError(
                f"User wallet '{wallet['name']}' uses scale mode, must specify 'scale_percentage'"
            )

        # Validate order type
        order_type = strategy.get('order_type', 'market')
        if order_type not in ['market', 'limit']:
            raise ValueError(
                f"User wallet '{wallet['name']}' order_type must be 'market' or 'limit', current value: {order_type}"
            )

        # Validate signature_type and proxy configuration
        signature_type = wallet.get('signature_type', 0)
        if signature_type not in [0, 1, 2]:
            raise ValueError(
                f"User wallet '{wallet['name']}' signature_type must be 0, 1 or 2, current value: {signature_type}"
            )

        # If using proxy mode (signature_type=2), must configure proxy_address
        if signature_type == 2:
            if 'proxy_address' not in wallet or not wallet['proxy_address']:
                raise ValueError(
                    f"User wallet '{wallet['name']}' uses signature_type=2 (proxy mode), "
                    f"must configure 'proxy_address' (Polymarket proxy contract address)"
                )

        # Set default values
        wallet.setdefault('signature_type', 0)  # Default to EOA mode
        strategy.setdefault('min_trigger_amount', 0)
        strategy.setdefault('max_trade_amount', 0)  # 0 means no limit
        strategy.setdefault('order_type', 'market')
        strategy.setdefault('limit_order_duration', 7200)

        validated.append(wallet)

    return validated


def load_private_key(wallet_config: dict) -> str:
    """
    Securely load user wallet private key.

    Args:
        wallet_config: Wallet configuration dictionary

    Returns:
        Private key string

    Raises:
        ValueError: Private key loading failed
    """
    if 'private_key_env' in wallet_config:
        env_var = wallet_config['private_key_env']
        key = os.environ.get(env_var)
        if not key:
            raise ValueError(
                f"Environment variable '{env_var}' not set, cannot load wallet '{wallet_config['name']}' private key"
            )
        return key
    else:
        raise ValueError(
            f"Wallet '{wallet_config['name']}' must specify 'private_key_env' field"
        )
