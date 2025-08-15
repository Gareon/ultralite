"""Sensor platform for UltraLite PRO Energy Meter."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import UltraLiteProCoordinator

_LOGGER = logging.getLogger(__name__)

# Sensor configuration mapping
SENSOR_TYPES = {
    "energy_total": {
        "name": "Total Energy",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "icon": "mdi:lightning-bolt",
    },
    "volume_total": {
        "name": "Total Volume",
        "device_class": SensorDeviceClass.VOLUME,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfVolume.CUBIC_METERS,
        "icon": "mdi:water",
    },
    "volume_flow": {
        "name": "Volume Flow Rate",
        "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        "icon": "mdi:pipe",
    },
    "flow_temperature": {
        "name": "Flow Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-chevron-up",
    },
    "return_temperature": {
        "name": "Return Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer-chevron-down",
    },
    "delta_temperature": {
        "name": "Temperature Difference",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfTemperature.KELVIN,
        "icon": "mdi:thermometer-minus",
    },
    "thermal_power": {
        "name": "Thermal Power",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "unit": UnitOfPower.KILO_WATT,
        "icon": "mdi:fire",
    },
    "operating_time_days": {
        "name": "Operating Time",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfTime.DAYS,
        "icon": "mdi:clock-outline",
    },
    "serial_number": {
        "name": "Serial Number",
        "device_class": None,
        "state_class": None,
        "unit": None,
        "icon": "mdi:identifier",
    },
    "firmware_version": {
        "name": "Firmware Version",
        "device_class": None,
        "state_class": None,
        "unit": None,
        "icon": "mdi:chip",
    },
    "software_version": {
        "name": "Software Version",
        "device_class": None,
        "state_class": None,
        "unit": None,
        "icon": "mdi:application-cog",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UltraLite PRO sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Create sensors for all available data points
    sensors = []
    for sensor_key in SENSOR_TYPES:
        sensors.append(UltraLiteProSensor(coordinator, config_entry, sensor_key))
    
    async_add_entities(sensors)


class UltraLiteProSensor(CoordinatorEntity, SensorEntity):
    """Representation of a UltraLite PRO sensor."""

    def __init__(
        self,
        coordinator: UltraLiteProCoordinator,
        config_entry: ConfigEntry,
        sensor_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sensor_key = sensor_key
        self._sensor_config = SENSOR_TYPES[sensor_key]
        
        # Use config entry ID as fallback for device serial
        self._device_serial = config_entry.entry_id
        
        # Entity attributes
        self._attr_name = self._sensor_config["name"]
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_key}"
        self._attr_device_class = self._sensor_config.get("device_class")
        self._attr_state_class = self._sensor_config.get("state_class")
        self._attr_native_unit_of_measurement = self._sensor_config.get("unit")
        self._attr_icon = self._sensor_config.get("icon")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Get device info from coordinator data if available
        device_data = self.coordinator.data or {}
        device_id = device_data.get("device_id", "unknown")
        serial_number = device_data.get("serial_number", {}).get("value") if device_data.get("serial_number") else None
        
        device_serial = serial_number or str(device_id) or self._config_entry.entry_id
        
        # Update unique_id and device_serial if we have real data
        if serial_number and self._device_serial == self._config_entry.entry_id:
            self._device_serial = serial_number
            self._attr_unique_id = f"{serial_number}_{self._sensor_key}"
        
        return DeviceInfo(
            identifiers={(DOMAIN, device_serial)},
            name=f"{MANUFACTURER} {MODEL}",
            manufacturer=MANUFACTURER,
            model=MODEL,
            serial_number=device_serial,
            sw_version=self._get_software_version(),
            hw_version=self._get_firmware_version(),
        )

    def _get_software_version(self) -> Optional[str]:
        """Get software version from coordinator data."""
        if self.coordinator.data and "software_version" in self.coordinator.data:
            sw_data = self.coordinator.data["software_version"]
            if isinstance(sw_data, dict) and "value" in sw_data:
                return str(sw_data["value"])
        return None

    def _get_firmware_version(self) -> Optional[str]:
        """Get firmware version from coordinator data."""
        if self.coordinator.data and "firmware_version" in self.coordinator.data:
            fw_data = self.coordinator.data["firmware_version"]
            if isinstance(fw_data, dict) and "value" in fw_data:
                return str(fw_data["value"])
        return None

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
            
        sensor_data = self.coordinator.data.get(self._sensor_key)
        if sensor_data is None:
            return None
            
        if isinstance(sensor_data, dict) and "value" in sensor_data:
            value = sensor_data["value"]
            
            # Handle special formatting for certain sensors
            if self._sensor_key in ["firmware_version", "software_version"]:
                return str(value) if value is not None else None
            elif self._sensor_key == "serial_number":
                return str(value) if value else None
            
            return value
        
        return sensor_data

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        if self.coordinator.data:
            # Add device information for certain sensors
            if self._sensor_key == "serial_number":
                device_data = self.coordinator.data
                if "device_id" in device_data:
                    attrs["device_id"] = device_data["device_id"]
                if "manufacturer" in device_data:
                    attrs["manufacturer"] = device_data["manufacturer"]
                if "version" in device_data:
                    attrs["version"] = device_data["version"]
                if "medium" in device_data:
                    attrs["medium"] = device_data["medium"]
                if "access_no" in device_data:
                    attrs["access_number"] = device_data["access_no"]
                if "status" in device_data:
                    attrs["status"] = device_data["status"]
        
        return attrs
