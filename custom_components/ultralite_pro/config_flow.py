"""Config flow for UltraLite PRO Energy Meter integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_USB_PATH,
    CONF_UPDATE_INTERVAL,
    CONF_PRIMARY_ADDRESS,
    DEFAULT_USB_PATH,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_PRIMARY_ADDRESS,
    ERROR_USB_NOT_FOUND,
    ERROR_DEVICE_NOT_RESPONDING,
    ERROR_PERMISSION_DENIED,
)
from .mbus import MBusReader

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USB_PATH, default=DEFAULT_USB_PATH): cv.string,
    vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
        cv.positive_int, vol.Range(min=10, max=3600)
    ),
    vol.Required(CONF_PRIMARY_ADDRESS, default=f"0x{DEFAULT_PRIMARY_ADDRESS:02X}"): cv.string,
})


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    
    # Parse primary address
    try:
        if data[CONF_PRIMARY_ADDRESS].startswith("0x"):
            primary_address = int(data[CONF_PRIMARY_ADDRESS], 16)
        else:
            primary_address = int(data[CONF_PRIMARY_ADDRESS])
        if not (0 <= primary_address <= 255):
            raise ValueError("Primary address must be between 0 and 255")
    except ValueError as e:
        raise InvalidPrimaryAddress from e
    
    # Test connection
    reader = MBusReader(data[CONF_USB_PATH], primary_address)
    
    try:
        if not await reader.connect():
            raise CannotConnect
        
        # Try to read data to validate the device responds
        meter_data = await reader.read_data()
        
        # Extract device information for unique_id
        device_id = meter_data.get("device_id")
        serial_number = meter_data.get("serial_number", {}).get("value") if meter_data.get("serial_number") else None
        
        if not device_id and not serial_number:
            raise DeviceNotResponding
            
        title = f"UltraLite PRO {serial_number or device_id}"
        
        return {
            "title": title,
            "device_id": device_id,
            "serial_number": serial_number,
            "primary_address": primary_address,
        }
        
    except Exception as e:
        if "Permission denied" in str(e):
            raise PermissionDenied from e
        elif "No such file or directory" in str(e):
            raise USBNotFound from e
        elif "No valid data" in str(e):
            raise DeviceNotResponding from e
        else:
            _LOGGER.error("Unexpected error during validation: %s", e)
            raise CannotConnect from e
    finally:
        reader.disconnect()


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UltraLite PRO Energy Meter."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except USBNotFound:
            errors[CONF_USB_PATH] = ERROR_USB_NOT_FOUND
        except PermissionDenied:
            errors[CONF_USB_PATH] = ERROR_PERMISSION_DENIED
        except DeviceNotResponding:
            errors["base"] = ERROR_DEVICE_NOT_RESPONDING
        except InvalidPrimaryAddress:
            errors[CONF_PRIMARY_ADDRESS] = "invalid_address"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Create unique_id from device info
            unique_id = info["serial_number"] or str(info["device_id"])
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=info["title"], 
                data={
                    **user_input,
                    CONF_PRIMARY_ADDRESS: info["primary_address"],
                }
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class USBNotFound(HomeAssistantError):
    """Error to indicate USB device not found."""


class PermissionDenied(HomeAssistantError):
    """Error to indicate permission denied."""


class DeviceNotResponding(HomeAssistantError):
    """Error to indicate device not responding."""


class InvalidPrimaryAddress(HomeAssistantError):
    """Error to indicate invalid primary address."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for UltraLite PRO Energy Meter."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        
        if user_input is not None:
            try:
                # Validate the input like in the main config flow
                await validate_input(self.hass, user_input)
                
                # Parse primary address for storage
                if user_input[CONF_PRIMARY_ADDRESS].startswith("0x"):
                    primary_address = int(user_input[CONF_PRIMARY_ADDRESS], 16)
                else:
                    primary_address = int(user_input[CONF_PRIMARY_ADDRESS])
                
                # Update the config entry data
                new_data = {**self.config_entry.data}
                new_data[CONF_USB_PATH] = user_input[CONF_USB_PATH]
                new_data[CONF_UPDATE_INTERVAL] = user_input[CONF_UPDATE_INTERVAL]
                new_data[CONF_PRIMARY_ADDRESS] = primary_address
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                
                return self.async_create_entry(title="", data={})
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except USBNotFound:
                errors[CONF_USB_PATH] = ERROR_USB_NOT_FOUND
            except PermissionDenied:
                errors[CONF_USB_PATH] = ERROR_PERMISSION_DENIED
            except DeviceNotResponding:
                errors["base"] = ERROR_DEVICE_NOT_RESPONDING
            except InvalidPrimaryAddress:
                errors[CONF_PRIMARY_ADDRESS] = "invalid_address"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Create schema with current values as defaults
        current_usb_path = self.config_entry.data.get(CONF_USB_PATH, DEFAULT_USB_PATH)
        current_interval = self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        current_address = self.config_entry.data.get(CONF_PRIMARY_ADDRESS, DEFAULT_PRIMARY_ADDRESS)
        
        # Format address for display
        if isinstance(current_address, int):
            address_display = f"0x{current_address:02X}"
        else:
            address_display = str(current_address)

        options_schema = vol.Schema({
            vol.Required(CONF_USB_PATH, default=current_usb_path): cv.string,
            vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): vol.All(
                cv.positive_int, vol.Range(min=10, max=3600)
            ),
            vol.Required(CONF_PRIMARY_ADDRESS, default=address_display): cv.string,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
