import logging
import multiprocessing
import signal
import sys
from typing import NoReturn

import uvicorn

from .monitor_wan1 import main as monitor_main

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_monitor() -> NoReturn:
    """Run the WAN1 monitoring service"""
    try:
        logger.info("Starting monitoring service process")
        monitor_main()
    except Exception as e:
        logger.error(f"Monitoring service crashed: {e}")
        sys.exit(1)


def run_api() -> NoReturn:
    """Run the FastAPI server"""
    try:
        logger.info("Starting API server process on port 8000")
        uvicorn.run(
            "src.api:app",
            host="0.0.0.0",
            port=3051,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"API server crashed: {e}")
        sys.exit(1)


def main() -> None:
    """Main supervisor process"""
    logger.info("Starting Shelly Starlink Control Services")

    # Create processes
    monitor_process = multiprocessing.Process(target=run_monitor, name="monitor")
    api_process = multiprocessing.Process(target=run_api, name="api")

    # Handle shutdown signals
    def signal_handler(signum, frame):
        logger.info("Shutdown signal received, stopping all processes")
        if monitor_process.is_alive():
            monitor_process.terminate()
        if api_process.is_alive():
            api_process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start both processes
    monitor_process.start()
    api_process.start()

    logger.info(f"Monitor process started (PID: {monitor_process.pid})")
    logger.info(f"API process started (PID: {api_process.pid})")

    # Monitor processes and restart if needed
    try:
        while True:
            # Check if monitor process died
            if not monitor_process.is_alive():
                logger.error("Monitor process died, shutting down")
                if api_process.is_alive():
                    api_process.terminate()
                    api_process.join(timeout=5)
                sys.exit(1)

            # Check if API process died
            if not api_process.is_alive():
                logger.error("API process died, shutting down")
                if monitor_process.is_alive():
                    monitor_process.terminate()
                    monitor_process.join(timeout=5)
                sys.exit(1)

            # Wait a bit before checking again
            monitor_process.join(timeout=1)
            api_process.join(timeout=1)

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down")
        if monitor_process.is_alive():
            monitor_process.terminate()
        if api_process.is_alive():
            api_process.terminate()
        sys.exit(0)


if __name__ == "__main__":
    main()
