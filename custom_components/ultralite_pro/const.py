"""Constants for the UltraLite PRO Energy Meter integration."""

DOMAIN = "ultralite_pro"

# Configuration
CONF_USB_PATH = "usb_path"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_PRIMARY_ADDRESS = "primary_address"

# Defaults
DEFAULT_USB_PATH = "/dev/ttyUSB0"
DEFAULT_UPDATE_INTERVAL = 60  # seconds
DEFAULT_PRIMARY_ADDRESS = 0xFE

# Error states
ERROR_USB_NOT_FOUND = "usb_device_not_found"
ERROR_DEVICE_NOT_RESPONDING = "target_device_not_responding"
ERROR_RESPONSE_NOT_UNDERSTOOD = "target_device_response_not_understood"
ERROR_PERMISSION_DENIED = "permission_denied"

# Services
SERVICE_UPDATE_SENSORS = "update_sensors"

# Device info
MANUFACTURER = "Itron"
MODEL = "UltraLite PRO"
