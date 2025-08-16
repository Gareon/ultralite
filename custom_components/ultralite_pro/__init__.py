"""The UltraLite PRO Energy Meter integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    SERVICE_UPDATE_SENSORS,
)
from .coordinator import UltraLiteProCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UltraLite PRO Energy Meter from a config entry."""
    
    # Get update interval from config, default to 60 seconds
    update_interval_seconds = entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    
    # Handle case where user sets interval to 0 (disable automatic updates)
    if update_interval_seconds == 0:
        update_interval = None
        _LOGGER.info("Automatic updates disabled for UltraLite PRO meter")
    else:
        update_interval = timedelta(seconds=update_interval_seconds)
        _LOGGER.info("Update interval set to %d seconds", update_interval_seconds)
    
    # Create coordinator
    coordinator = UltraLiteProCoordinator(hass, entry, update_interval)
    
    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()
    
    # Forward entry setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    # Register services
    await _async_register_services(hass)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
        
        # Remove services if this was the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_UPDATE_SENSORS)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    
    async def handle_update_sensors(call: ServiceCall) -> None:
        """Handle the update sensors service call."""
        # Get target device from service call
        device_id = call.data.get("device_id")
        
        if device_id:
            # Update specific device
            device_registry = dr.async_get(hass)
            device = device_registry.async_get(device_id)
            
            if not device:
                _LOGGER.error("Device %s not found", device_id)
                return
            
            # Find the config entry for this device
            config_entry_id = None
            for identifier in device.identifiers:
                if identifier[0] == DOMAIN:
                    # Find config entry with matching device
                    for entry_id, coordinator in hass.data[DOMAIN].items():
                        if coordinator.data and hasattr(coordinator, '_device_serial'):
                            if coordinator._device_serial == identifier[1]:
                                config_entry_id = entry_id
                                break
                    break
            
            if config_entry_id and config_entry_id in hass.data[DOMAIN]:
                coordinator = hass.data[DOMAIN][config_entry_id]
                success = await coordinator.async_manual_update()
                if success:
                    _LOGGER.info("Successfully updated sensors for device %s", device_id)
                else:
                    _LOGGER.error("Failed to update sensors for device %s", device_id)
            else:
                _LOGGER.error("No coordinator found for device %s", device_id)
        else:
            # Update all devices
            updated_count = 0
            for coordinator in hass.data[DOMAIN].values():
                success = await coordinator.async_manual_update()
                if success:
                    updated_count += 1
            
            _LOGGER.info("Updated %d UltraLite PRO devices", updated_count)
    
    # Register service only if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_UPDATE_SENSORS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_UPDATE_SENSORS,
            handle_update_sensors,
            schema=vol.Schema({
                vol.Optional("device_id"): cv.string,
            }),
        )
