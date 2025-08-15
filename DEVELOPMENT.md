# Manual Home Assistant Development Setup

## Option A: Docker Development Environment

### 1. Quick Start with Docker
```bash
# Run the setup script
./setup_ha_dev.sh

# Start Home Assistant
cd ha_dev
docker-compose up -d

# View logs
docker-compose logs -f homeassistant
```

### 2. Access Home Assistant
- Open: http://localhost:8123
- Complete initial setup (create user account)
- Go to Settings → Devices & Services → Add Integration
- Search for "UltraLite PRO"

## Option B: Python Virtual Environment

### 1. Install Home Assistant Core
```bash
# Create virtual environment
python3 -m venv ha_venv
source ha_venv/bin/activate

# Install Home Assistant
pip install homeassistant

# Create config directory
mkdir -p ~/.homeassistant/custom_components
cp -r custom_components/ultralite_pro ~/.homeassistant/custom_components/
```

### 2. Start Home Assistant
```bash
source ha_venv/bin/activate
hass --open-ui
```

## Option C: Home Assistant Development Environment

### 1. Clone HA Core for Development
```bash
git clone https://github.com/home-assistant/core.git ha-core
cd ha-core

# Install development requirements
pip install -e .
pip install -r requirements_dev.txt
```

### 2. Add Your Integration
```bash
# Copy integration to HA core
cp -r /path/to/custom_components/ultralite_pro homeassistant/components/

# Run tests
python -m pytest tests/components/ultralite_pro/
```

## Testing Strategies

### 1. Integration Testing
Test the integration without hardware using mock data:

```python
# Create test_integration_mock.py
import asyncio
from custom_components.ultralite_pro.mbus import MBusReader

# Mock the hardware calls
class MockMBusReader(MBusReader):
    async def read_data(self):
        return {
            "device_id": 22106352,
            "serial_number": {"value": "22106352", "unit": None},
            "energy_total": {"value": 11570.0, "unit": "kWh"},
            "volume_total": {"value": 355.04, "unit": "m³"},
            "volume_flow": {"value": 0.295, "unit": "m³/h"},
            "flow_temperature": {"value": 40.2, "unit": "°C"},
            "return_temperature": {"value": 30.8, "unit": "°C"},
            "delta_temperature": {"value": 9.35, "unit": "K"},
            "thermal_power": {"value": 3.208, "unit": "kW"},
            "operating_time_days": {"value": 1095, "unit": "days"},
            "firmware_version": {"value": 8, "unit": None},
            "software_version": {"value": 11, "unit": None},
        }
```

### 2. Unit Testing
```bash
# Test individual components
python3 test_mbus_only.py

# Test with actual hardware (if connected)
python3 read_ultralite_pyserial.py --debug
```

### 3. Configuration Testing
Test config flow without starting full HA:

```python
# test_config_flow.py
from custom_components.ultralite_pro.config_flow import validate_input

# Test with mock USB device
test_data = {
    "usb_path": "/dev/ttyUSB0",
    "update_interval": 60,
    "primary_address": "0xFE"
}

# This would normally test actual hardware
# result = await validate_input(hass, test_data)
```

## Development Workflow

### 1. Code → Test → Deploy Cycle
```bash
# 1. Make changes to integration code
vim custom_components/ultralite_pro/sensor.py

# 2. Copy to development environment
cp -r custom_components/ultralite_pro ha_dev/custom_components/

# 3. Restart Home Assistant
cd ha_dev
docker-compose restart homeassistant

# 4. Check logs
docker-compose logs -f homeassistant | grep ultralite_pro
```

### 2. Debug Common Issues
```bash
# Check USB device permissions
ls -la /dev/ttyUSB0
sudo usermod -a -G dialout $USER

# Monitor USB device connections
dmesg | grep ttyUSB

# Test M-Bus communication directly
python3 read_ultralite_pyserial.py --debug
```

### 3. Enable Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.ultralite_pro: debug
    custom_components.ultralite_pro.mbus: debug
    custom_components.ultralite_pro.coordinator: debug
```

## Useful Development Commands

### Docker Environment
```bash
# Start HA development environment
./setup_ha_dev.sh && cd ha_dev && docker-compose up -d

# View live logs
docker-compose logs -f homeassistant

# Restart after code changes
docker-compose restart homeassistant

# Shell into container
docker-compose exec homeassistant bash

# Stop environment
docker-compose down
```

### Testing Commands
```bash
# Test integration structure
python3 test_integration.py

# Test M-Bus functionality
python3 test_mbus_only.py

# Test with real hardware
python3 read_ultralite_pyserial.py --debug

# Check USB devices
ls -la /dev/ttyUSB*
```

## Troubleshooting

### Common Development Issues

1. **Permission Denied on USB Device**
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in
   ```

2. **Integration Not Loading**
   - Check logs for import errors
   - Verify file structure
   - Restart Home Assistant

3. **USB Device Not Found**
   ```bash
   # Find USB devices
   lsusb
   dmesg | grep ttyUSB
   
   # Test device
   python3 read_ultralite_pyserial.py /dev/ttyUSB0
   ```

4. **Config Flow Errors**
   - Enable debug logging
   - Check config_flow.py for validation issues
   - Test with mock data first
