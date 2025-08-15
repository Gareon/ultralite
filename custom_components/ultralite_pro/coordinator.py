"""Data update coordinator for UltraLite PRO Energy Meter."""

import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import serial

from .const import DOMAIN, CONF_USB_PATH, CONF_PRIMARY_ADDRESS
from .mbus import MBusReader

_LOGGER = logging.getLogger(__name__)


class UltraLiteProCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from UltraLite PRO meter."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.config_entry = config_entry
        self.usb_path = config_entry.data[CONF_USB_PATH]
        self.primary_address = config_entry.data[CONF_PRIMARY_ADDRESS]
        
        self.reader = MBusReader(self.usb_path, self.primary_address)
        self._retry_count = 0
        self._max_retries = 3
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via library."""
        try:
            data = await self._fetch_data_with_retry()
            self._retry_count = 0  # Reset retry count on success
            return data
        except Exception as e:
            _LOGGER.error("Error communicating with meter: %s", e)
            raise UpdateFailed(f"Error communicating with meter: {e}") from e

    async def _fetch_data_with_retry(self) -> Dict[str, Any]:
        """Fetch data with exponential backoff retry."""
        last_exception = None
        
        for attempt in range(self._max_retries):
            try:
                data = await self.reader.read_data()
                return data
            except serial.SerialException as e:
                last_exception = e
                error_msg = str(e).lower()
                
                if "permission denied" in error_msg:
                    raise UpdateFailed("Permission denied accessing USB device") from e
                elif "no such file or directory" in error_msg:
                    raise UpdateFailed("USB device not found") from e
                elif "input/output error" in error_msg:
                    # Device was disconnected, try to reconnect
                    _LOGGER.warning("Device disconnected, attempting reconnection (attempt %d/%d)", 
                                  attempt + 1, self._max_retries)
                    self.reader.disconnect()
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise UpdateFailed(f"Serial communication error: {e}") from e
            except Exception as e:
                last_exception = e
                if "No valid data" in str(e):
                    _LOGGER.warning("No valid data received (attempt %d/%d)", 
                                  attempt + 1, self._max_retries)
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise UpdateFailed(f"Unexpected error: {e}") from e
        
        # All retries exhausted
        if "input/output error" in str(last_exception).lower():
            raise UpdateFailed("Device not responding (device may be disconnected)") from last_exception
        elif "No valid data" in str(last_exception):
            raise UpdateFailed("Target device response not understood") from last_exception
        else:
            raise UpdateFailed(f"Failed after {self._max_retries} attempts: {last_exception}") from last_exception

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        self.reader.disconnect()

    async def async_manual_update(self) -> bool:
        """Manually update data."""
        try:
            await self.async_request_refresh()
            return True
        except UpdateFailed:
            return False
