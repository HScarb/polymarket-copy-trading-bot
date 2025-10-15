"""
Activity logging utilities.

Provides formatted logging for wallet activities.
"""

from typing import Any, Optional

from src.logger import log
from src.utils.time_utils import format_timestamp_for_display


def build_market_link(event_slug: Optional[str]) -> str:
    """
    Build Polymarket market link from event slug.

    Args:
        event_slug: Event slug from activity

    Returns:
        Market URL or 'N/A' if no slug provided
    """
    if event_slug:
        return f"https://polymarket.com/event/{event_slug}"
    return "N/A"


def get_trade_value(activity: Any) -> float:
    """
    Calculate trade value in USDC from activity.

    Args:
        activity: Activity object

    Returns:
        Trade value in USDC
    """
    cash_amount = getattr(activity, 'cash_amount', 0)
    if cash_amount > 0:
        return float(cash_amount)

    # If cash_amount is 0, calculate from size × price
    size = float(getattr(activity, 'size', 0))
    price = float(getattr(activity, 'price', 0))
    return size * price


def log_activity(wallet_address: str, activity: Any) -> None:
    """
    Log activity information in a formatted block.

    Args:
        wallet_address: Wallet address
        activity: Activity object with attributes (type, title, outcome, etc.)
    """
    # Extract basic information
    activity_type = getattr(activity, 'type', 'N/A')
    condition_id = getattr(activity, 'condition_id', 'N/A')
    user_name = getattr(activity, 'name', None)
    market_title = getattr(activity, 'title', 'N/A')
    outcome = getattr(activity, 'outcome', 'N/A')
    side = getattr(activity, 'side', 'N/A')
    event_slug = getattr(activity, 'event_slug', None)

    # Extract amounts
    size = getattr(activity, 'size', 0)
    price = getattr(activity, 'price', 0)
    cash_amount = get_trade_value(activity)

    # Build market link
    market_link = build_market_link(event_slug)

    # Format timestamp
    timestamp_raw = getattr(activity, 'timestamp', None)
    timestamp = format_timestamp_for_display(timestamp_raw)

    # Display wallet with name if available
    wallet_display = f"{wallet_address} ({user_name})" if user_name else wallet_address

    # Log in block format
    log.info("╔════════════════════════════════════════════════════╗")
    log.info(f"║ Wallet: {wallet_display}")
    log.info(f"║ Type: {activity_type} {side}")
    log.info(f"║ Market: {market_title}")
    log.info(f"║ condition_id: {condition_id}")
    log.info(f"║ Outcome: {outcome}")
    log.info(f"║ Size: {float(size):.4f} | Price: ${float(price):.4f} | Total: ${cash_amount:.2f}")
    log.info(f"║ Time: {timestamp}")
    log.info(f"║ Link: {market_link}")
    log.info("╚════════════════════════════════════════════════════╝")


def log_activities(wallet_address: str, activities: list) -> None:
    """
    Log multiple activities.

    Args:
        wallet_address: Wallet address
        activities: List of activity objects
    """
    for activity in activities:
        log_activity(wallet_address, activity)
