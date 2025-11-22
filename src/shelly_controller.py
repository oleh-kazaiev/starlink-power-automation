import json
import logging
import os
from enum import Enum
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class ControlMode(str, Enum):
    """Control modes for Shelly plug"""
    ON = "on"
    OFF = "off"
    AUTO = "auto"


class ShellyController:
    """Controller for managing Shelly plug state and modes"""

    STATE_FILE = '/app/state.json'

    def __init__(self):
        """Initialize the Shelly controller"""
        self.shelly_base_url = os.getenv('SHELLY_BASE_URL')
        if not self.shelly_base_url:
            raise ValueError('SHELLY_BASE_URL environment variable must be set')

    def load_state(self) -> dict:
        """Load state from JSON file"""
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f'Error loading state: {e}')

        return {
            'consecutive_failures': 0,
            'plug_on': False,
            'last_wan1_online_time': None,
            'mode': ControlMode.AUTO.value
        }

    def save_state(self, state: dict) -> None:
        """Save state to JSON file"""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f'Error saving state: {e}')

    def control_plug(self, turn_on: bool) -> bool:
        """
        Control Shelly plug on/off state.

        Args:
            turn_on: True to turn on, False to turn off

        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {'id': 0, 'on': turn_on}
            response = requests.post(
                f'{self.shelly_base_url}/rpc/Switch.Set',
                json=payload,
                timeout=5
            )
            if response.status_code == 200:
                state_str = 'ON' if turn_on else 'OFF'
                logger.info(f'Shelly plug turned {state_str}')
                return True
            else:
                logger.warning(f'Failed to control plug: {response.status_code}')
                return False
        except Exception as e:
            logger.error(f'Error controlling Shelly plug: {e}')
            return False

    def get_plug_status(self) -> Optional[bool]:
        """
        Get current Shelly plug status.

        Returns:
            True if on, False if off, None if error
        """
        try:
            response = requests.post(
                f'{self.shelly_base_url}/rpc/Switch.GetStatus',
                json={'id': 0},
                timeout=5
            )
            if response.status_code == 200:
                result = response.json()
                is_on = result.get('output', False)
                return is_on
            else:
                logger.warning(f'Failed to get plug status: {response.status_code}')
                return None
        except Exception as e:
            logger.error(f'Error getting Shelly plug status: {e}')
            return None

    def set_mode(self, mode: ControlMode) -> bool:
        """
        Set the operating mode and apply it.

        Args:
            mode: The control mode to set

        Returns:
            True if successful, False otherwise
        """
        try:
            state = self.load_state()
            old_mode = state.get('mode', ControlMode.AUTO.value)
            state['mode'] = mode.value

            # Apply the mode immediately
            if mode == ControlMode.ON:
                # Turn plug ON and update state
                if self.control_plug(True):
                    state['plug_on'] = True
                    state['consecutive_failures'] = 0
                    state['last_wan1_online_time'] = None
                    logger.info(f'Mode changed from {old_mode} to ON - plug turned ON')
                else:
                    return False

            elif mode == ControlMode.OFF:
                # Turn plug OFF and update state
                if self.control_plug(False):
                    state['plug_on'] = False
                    state['consecutive_failures'] = 0
                    state['last_wan1_online_time'] = None
                    logger.info(f'Mode changed from {old_mode} to OFF - plug turned OFF')
                else:
                    return False

            elif mode == ControlMode.AUTO:
                # Reset to auto mode - don't change plug state
                # Let the monitoring service handle it
                state['consecutive_failures'] = 0
                state['last_wan1_online_time'] = None
                logger.info(f'Mode changed from {old_mode} to AUTO - monitoring service will control plug')

            self.save_state(state)
            return True

        except Exception as e:
            logger.error(f'Error setting mode: {e}')
            return False

    def get_status(self) -> dict:
        """
        Get current system status.

        Returns:
            Dictionary with current mode, plug state, and monitoring info
        """
        state = self.load_state()
        plug_status = self.get_plug_status()

        return {
            'mode': state.get('mode', ControlMode.AUTO.value),
            'plug_on': plug_status if plug_status is not None else state.get('plug_on', False),
            'consecutive_failures': state.get('consecutive_failures', 0),
            'last_wan1_online_time': state.get('last_wan1_online_time')
        }
