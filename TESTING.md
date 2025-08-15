# Development Testing Workflow for UltraLite PRO Integration

## Quick Start Guide

### 1. Test Integration Logic (No Hardware Required)
```bash
# Test core M-Bus functionality
./test_mbus_only.py

# Test integration components with mock data
./test_integration_mock.py
```

### 2. Test with Your Hardware
```bash
# Test USB setup and permissions
./test_hardware.py

# Test with your existing script
python3 read_ultralite_pyserial.py --debug
```

### 3. Set Up Home Assistant Development Environment
```bash
# Create HA development setup
./setup_ha_dev.sh

# Start Home Assistant
cd ha_dev && docker-compose up -d

# Access at http://localhost:8123
```

## Detailed Testing Options

### Option A: Mock Testing (Recommended for Logic Testing)

**Benefits:**
- No hardware required
- Fast iteration
- Test error conditions easily
- Safe for CI/CD

**Commands:**
```bash
# Basic M-Bus function testing
python3 test_mbus_only.py

# Full integration mock testing
python3 test_integration_mock.py
```

### Option B: Hardware Testing (Recommended for Final Validation)

**Benefits:**
- Tests real communication
- Validates actual device responses
- Confirms USB setup

**Commands:**
```bash
# Check USB device setup
python3 test_hardware.py

# Test with debug output
python3 read_ultralite_pyserial.py --debug

# Test specific functionality
python3 read_ultralite_pyserial.py /dev/ttyUSB0 --addr 0xFE --window 3.0
```

### Option C: Home Assistant Integration Testing

**Benefits:**
- Full end-to-end testing
- UI testing
- Service testing
- Energy dashboard integration

**Setup:**
```bash
# Quick setup
./setup_ha_dev.sh
cd ha_dev
docker-compose up -d

# Manual setup
mkdir -p ~/.homeassistant/custom_components
cp -r custom_components/ultralite_pro ~/.homeassistant/custom_components/
```

## Development Workflow

### 1. Development Cycle
```bash
# 1. Make code changes
vim custom_components/ultralite_pro/sensor.py

# 2. Test locally
python3 test_integration_mock.py

# 3. Test with hardware (if available)
python3 test_hardware.py

# 4. Update HA development environment
cp -r custom_components/ultralite_pro ha_dev/custom_components/
cd ha_dev && docker-compose restart homeassistant

# 5. Check HA logs
docker-compose logs -f homeassistant | grep ultralite_pro
```

### 2. Debug Issues

**Import Errors:**
```bash
python3 test_integration.py  # Shows what's missing
pip install voluptuous pyserial  # Install dependencies
```

**USB Permission Issues:**
```bash
ls -la /dev/ttyUSB*  # Check device exists
sudo chmod 666 /dev/ttyUSB0  # Quick fix
sudo usermod -a -G dialout $USER  # Permanent fix (requires logout)
```

**Communication Issues:**
```bash
python3 read_ultralite_pyserial.py --debug  # Raw M-Bus testing
dmesg | grep ttyUSB  # Check USB events
```

### 3. Home Assistant Testing

**Add Integration:**
1. Go to Settings → Devices & Services
2. Click "Add Integration" 
3. Search for "UltraLite PRO"
4. Follow configuration wizard

**Test Services:**
1. Go to Developer Tools → Services
2. Select `ultralite_pro.update_sensors`
3. Click "Call Service"

**Check Energy Dashboard:**
1. Settings → Dashboards → Energy
2. Add "Total Energy" sensor as energy source

## Test Scripts Overview

| Script | Purpose | Hardware Required |
|--------|---------|-------------------|
| `test_mbus_only.py` | Core M-Bus functions | No |
| `test_integration_mock.py` | Integration logic | No |
| `test_hardware.py` | Hardware communication | Yes |
| `test_integration.py` | File structure check | No |
| `read_ultralite_pyserial.py` | Original working script | Yes |

## Common Development Tasks

### Add New Sensor
1. Update `SENSOR_TYPES` in `sensor.py`
2. Add VIF mapping in `mbus.py` 
3. Test with mock data
4. Update translations in `translations/en.json`

### Change Configuration Options
1. Update `const.py` constants
2. Modify config flow in `config_flow.py`
3. Update validation logic
4. Test config flow in HA

### Improve Error Handling
1. Add error conditions to `coordinator.py`
2. Test with disconnected hardware
3. Verify sensor states become "unavailable"
4. Check error recovery

### Debug Communication Issues
```bash
# Enable debug logging in HA configuration.yaml
logger:
  logs:
    custom_components.ultralite_pro: debug

# Test with raw script
python3 read_ultralite_pyserial.py --debug --save debug.bin

# Analyze saved data
hexdump -C debug.bin
```

## Production Deployment

### Before Release
```bash
# 1. Run all tests
python3 test_mbus_only.py
python3 test_integration_mock.py
python3 test_hardware.py

# 2. Test in HA development environment
./setup_ha_dev.sh
cd ha_dev && docker-compose up -d
# Add integration via UI and test all features

# 3. Check file structure
find custom_components/ultralite_pro -name "*.py" -exec python3 -m py_compile {} \;
```

### Package for HACS
```bash
# Create release structure
mkdir ultralite_pro_release
cp -r custom_components/ultralite_pro ultralite_pro_release/
cp README.md ultralite_pro_release/
cp INSTALLATION.md ultralite_pro_release/

# Verify structure
tree ultralite_pro_release/
```

## Troubleshooting Guide

### "Integration not loading"
- Check HA logs for Python errors
- Verify file permissions
- Test imports with mock script

### "USB device not found"
- Check device connection: `ls -la /dev/ttyUSB*`
- Test with original script: `python3 read_ultralite_pyserial.py`
- Check USB events: `dmesg | grep ttyUSB`

### "Permission denied"
- Fix permissions: `sudo chmod 666 /dev/ttyUSB0`
- Add user to group: `sudo usermod -a -G dialout $USER`
- Restart HA container after permission changes

### "Device not responding"
- Check IR alignment between reader and meter
- Verify meter is not in deep sleep
- Test with debug output: `python3 read_ultralite_pyserial.py --debug`

### "Config flow fails"
- Enable debug logging
- Test validation logic separately
- Check config_flow.py for specific errors

This workflow gives you multiple testing approaches depending on your development phase and available hardware!
