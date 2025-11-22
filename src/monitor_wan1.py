import logging
import os
import signal
from datetime import datetime
from threading import Event

import requests
from urllib3.exceptions import InsecureRequestWarning

from .shelly_controller import ShellyController, ControlMode

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

OMADA_URL = os.getenv('OMADA_URL')
USERNAME = os.getenv('OMADA_USERNAME')
PASSWORD = os.getenv('OMADA_PASSWORD')
SITE_ID = os.getenv('OMADA_SITE_ID')
GATEWAY_MAC = os.getenv('OMADA_GATEWAY_MAC')

CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '10'))
FAILURE_THRESHOLD = int(os.getenv('FAILURE_THRESHOLD', '3'))
RECOVERY_DELAY = int(os.getenv('RECOVERY_DELAY', '600'))

shutdown_event = Event()
controller = ShellyController()


def check_wan1_status():
    """Check WAN1 internet status from Omada controller"""
    try:
        session = requests.Session()
        login = session.post(
            f'{OMADA_URL}/api/v2/login',
            json={'username': USERNAME, 'password': PASSWORD},
            verify=False,
            timeout=5
        ).json()

        if login.get('errorCode') == 0:
            result = login.get('result', {})
            omadac_id = result.get('omadacId')
            token = result.get('token')

            if not omadac_id or not token:
                logger.error('Missing omadacId or token in login response')
                return False

            gateway = session.get(
                f'{OMADA_URL}/{omadac_id}/api/v2/sites/{SITE_ID}/gateways/{GATEWAY_MAC}',
                headers={'Csrf-Token': token},
                verify=False,
                timeout=5
            ).json()

            if gateway.get('errorCode') == 0:
                result = gateway.get('result', {})
                port_stats = result.get('portStats', [])
                for port in port_stats:
                    if port.get('type') == 0 and port.get('port') == 1:
                        return port.get('internetState') == 1

        return False
    except Exception as e:
        logger.error(f'Error checking WAN1: {e}')
        return False


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info('Shutdown signal received')
    shutdown_event.set()


def main():
    """Main monitoring loop"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info('Starting WAN1 monitoring service...')

    # Initialize state with current plug status
    state = controller.load_state()
    current_plug_state = controller.get_plug_status()
    if current_plug_state is not None:
        state['plug_on'] = current_plug_state
        controller.save_state(state)

    while not shutdown_event.is_set():
        try:
            state = controller.load_state()
            current_mode = ControlMode(state.get('mode', ControlMode.AUTO.value))

            # Only run automatic monitoring if in AUTO mode
            if current_mode != ControlMode.AUTO:
                logger.debug(f'Mode is {current_mode.value}, skipping automatic monitoring')
                shutdown_event.wait(CHECK_INTERVAL)
                continue

            wan1_online = check_wan1_status()

            status = 'ONLINE' if wan1_online else 'OFFLINE'
            logger.info(f'WAN1: {status}')

            if wan1_online:
                state['consecutive_failures'] = 0

                if state.get('plug_on', False):
                    if state.get('last_wan1_online_time') is None:
                        state['last_wan1_online_time'] = datetime.now().isoformat()
                        logger.info('WAN1 back online. Starting recovery timer.')

                    last_online_time = state.get('last_wan1_online_time')
                    if last_online_time:
                        last_online = datetime.fromisoformat(last_online_time)
                        time_online = (datetime.now() - last_online).total_seconds()

                        if time_online >= RECOVERY_DELAY:
                            logger.info(f'WAN1 online for {time_online:.0f}s. Turning plug OFF.')
                            if controller.control_plug(False):
                                state['plug_on'] = False
                                state['last_wan1_online_time'] = None
                        else:
                            wait_time = RECOVERY_DELAY - time_online
                            logger.info(f'WAN1 online for {time_online:.0f}s. Waiting {wait_time:.0f}s more before turning plug OFF.')
            else:
                state['consecutive_failures'] = state.get('consecutive_failures', 0) + 1
                failures = state.get('consecutive_failures', 0)
                logger.warning(f'Consecutive failures: {failures}/{FAILURE_THRESHOLD}')

                if state.get('consecutive_failures', 0) >= FAILURE_THRESHOLD:
                    if not state.get('plug_on', False):
                        logger.warning(f'WAN1 failed {FAILURE_THRESHOLD} times. Turning plug ON.')
                        if controller.control_plug(True):
                            state['plug_on'] = True
                            state['last_wan1_online_time'] = None
                    else:
                        logger.debug('Plug already ON, no action needed.')

            controller.save_state(state)
            shutdown_event.wait(CHECK_INTERVAL)

        except Exception as e:
            logger.error(f'Error: {e}')
            shutdown_event.wait(CHECK_INTERVAL)

    logger.info('Service stopped gracefully')


if __name__ == '__main__':
    main()
