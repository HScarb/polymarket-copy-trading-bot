"""
Main entry point for Polymarket copy trading bot.

Initializes monitoring and copy trading components based on configuration.
"""

import logging
import signal
import sys

from src.config_loader import load_config
from src.logger import setup_logger
from src.wallet_monitor import WalletMonitor
from src.in_memory_activity_queue import InMemoryActivityQueue
from src.copy_trader import CopyTrader


def create_activity_queue(config: dict):
    """
    Create activity queue instance based on configuration.

    Args:
        config: Configuration dictionary

    Returns:
        ActivityQueue instance
    """
    queue_config = config.get('queue', {})
    queue_type = queue_config.get('type', 'memory')

    if queue_type == 'memory':
        memory_config = queue_config.get('memory', {})
        max_workers = memory_config.get('max_workers', 10)
        return InMemoryActivityQueue(max_workers=max_workers)
    elif queue_type == 'rabbitmq':
        # TODO: Implement RabbitMQ queue
        raise NotImplementedError("RabbitMQ queue not yet implemented")
    else:
        raise ValueError(f"Unsupported queue type: {queue_type}")


def main():
    """Program entry point."""
    try:
        # Load configuration
        config = load_config("config.yaml")

        # Configure logging
        log_config = config.get('logging', {})
        log_dir = log_config.get('log_dir', 'logs')
        log_level_str = log_config.get('level', 'INFO')
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Reinitialize logger
        log = setup_logger(log_dir=log_dir, level=log_level)
        log.info("Loading configuration file...")

        # Extract configuration
        monitoring_config = config['monitoring']
        wallets = monitoring_config['wallets']
        poll_interval = monitoring_config['poll_interval_seconds']
        batch_size = monitoring_config.get('batch_size', 500)
        api_config = config.get('polymarket_api', {})
        proxy = api_config.get('proxy')
        timeout = api_config.get('timeout', 30.0)

        # Extract Polygon RPC configuration
        polygon_rpc_config = config.get('polygon_rpc', {})

        # Create activity queue
        activity_queue = create_activity_queue(config)
        log.info(f"Activity queue created: {type(activity_queue).__name__}")

        # Initialize copy traders (if user wallets configured)
        copy_traders = []
        user_wallets = config.get('user_wallets', [])

        if user_wallets:
            log.info(f"Detected {len(user_wallets)} user wallet config(s), initializing copy traders...")

            for wallet_config in user_wallets:
                try:
                    trader = CopyTrader(
                        wallet_config=wallet_config,
                        activity_queue=activity_queue,
                        polygon_rpc_config=polygon_rpc_config
                    )
                    copy_traders.append(trader)

                    # Start copy trading for each target wallet
                    for target_wallet in wallets:
                        trader.run(target_wallet)

                    log.info(f"Copy trader '{wallet_config['name']}' started")

                except Exception as e:
                    log.error(
                        f"Failed to initialize copy trader '{wallet_config.get('name', 'unknown')}': {e}",
                        exc_info=True
                    )
        else:
            log.info("No user wallets configured, running in monitoring mode only (activities will be printed by WalletMonitor)")

        # Create monitor
        monitor = WalletMonitor(
            wallets=wallets,
            poll_interval=poll_interval,
            activity_queue=activity_queue,
            batch_size=batch_size,
            proxy=proxy,
            timeout=timeout
        )

        # Set up signal handler for graceful shutdown
        def signal_handler(sig, frame):
            log.info("Received exit signal, shutting down...")

            # Print copy trading statistics
            for trader in copy_traders:
                trader.print_stats()

            monitor.stop()
            if hasattr(activity_queue, 'shutdown'):
                activity_queue.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start monitoring
        monitor.start()

        # Keep main thread running
        log.info("Monitoring running, press Ctrl+C to exit...")
        while True:
            signal.pause() if hasattr(signal, 'pause') else monitor.stop_event.wait(3600)

    except FileNotFoundError as e:
        log.error(f"Configuration file error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Program startup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
