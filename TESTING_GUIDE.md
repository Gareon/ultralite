# Testing Guide for UltraLite PRO Integration

## 🧪 Available Test Scripts

### **1. Core Logic Testing (No Dependencies Required)**

#### `./test_standalone.py` ✅ **RECOMMENDED FOR DEVELOPMENT**
- **Purpose**: Test integration logic without Home Assistant
- **Requirements**: Only Python 3, no special dependencies
- **What it tests**: 
  - M-Bus data parsing with your actual meter values
  - Sensor definitions and Home Assistant device classes
  - Device information structure
  - Error handling scenarios
- **When to use**: During development, CI/CD, quick validation

```bash
./test_standalone.py
# Expected output: All tests pass, shows parsed sensor data
```

#### `./test_mbus_only.py` ✅ **BASIC FUNCTIONALITY**
- **Purpose**: Test core M-Bus functions only
- **Requirements**: Only Python 3
- **What it tests**: Basic parsing, VIF mapping, calculations
- **When to use**: Quick function validation

```bash
./test_mbus_only.py
# Expected output: Core M-Bus functions working correctly
```

### **2. Hardware Testing (Requires USB Device)**

#### `./test_hardware.py` ✅ **HARDWARE VALIDATION**
- **Purpose**: Test with real UltraLite PRO hardware
- **Requirements**: USB IR device connected, permissions set
- **What it tests**: 
  - USB device access and permissions
  - Real M-Bus communication
  - Multiple consecutive reads for stability
- **When to use**: Final validation, troubleshooting hardware issues

```bash
./test_hardware.py
# Expected output: Successful hardware communication with real sensor data
```

#### `python3 read_ultralite_pyserial.py` ✅ **REFERENCE IMPLEMENTATION**
- **Purpose**: Your original working script for comparison
- **Requirements**: USB IR device, pyserial
- **When to use**: Verify hardware works, compare output

```bash
python3 read_ultralite_pyserial.py --debug
# Expected output: Continuous meter readings with debug info
```

### **3. Home Assistant Integration Testing**

#### `./setup_ha_dev.sh && cd ha_dev && docker-compose up -d` ✅ **FULL INTEGRATION**
- **Purpose**: Test complete Home Assistant integration
- **Requirements**: Docker, USB device (optional for initial setup)
- **What it tests**: 
  - Config flow UI
  - Sensor entities
  - Services
  - Energy dashboard integration
- **When to use**: Final integration testing

```bash
./setup_ha_dev.sh
cd ha_dev && docker-compose up -d
# Access: http://localhost:8123
```

### **4. Deprecated/Problematic Tests**

#### ❌ `./test_integration_mock.py` - **DON'T USE**
- **Issue**: Requires Home Assistant dependencies (voluptuous, etc.)
- **Error**: `No module named 'voluptuous'`
- **Replacement**: Use `./test_standalone.py` instead

#### ❌ `./test_integration.py` - **LIMITED USE** 
- **Issue**: Also requires HA dependencies for full testing
- **Use**: Only for file structure checking
- **Replacement**: Use `./test_standalone.py` for logic testing

## 📋 **Recommended Testing Workflow**

### **For Daily Development:**
```bash
# 1. Quick logic validation (always works)
./test_standalone.py

# 2. If you have hardware connected
./test_hardware.py

# 3. Deploy to HA when ready
./setup_ha_dev.sh
cd ha_dev && docker-compose up -d
```

### **For Troubleshooting:**
```bash
# 1. Test core logic first
./test_standalone.py

# 2. Compare with reference implementation
python3 read_ultralite_pyserial.py --debug

# 3. Test hardware integration
./test_hardware.py

# 4. Check HA logs if needed
cd ha_dev && docker-compose logs -f homeassistant | grep ultralite_pro
```

### **For CI/CD or Remote Development:**
```bash
# Only test logic (no hardware required)
./test_standalone.py
./test_mbus_only.py
```

## 🔧 **Quick Start Commands**

```bash
# Test integration logic (always works)
./test_standalone.py

# Test with your hardware (requires USB device)
./test_hardware.py

# Set up Home Assistant development
./setup_ha_dev.sh && cd ha_dev && docker-compose up -d

# Access Home Assistant at http://localhost:8123
# Add integration: Settings → Devices & Services → Add Integration → "UltraLite PRO"
```

## 🐛 **Troubleshooting Test Issues**

### **"No module named 'voluptuous'"**
- **Solution**: Use `./test_standalone.py` instead of `./test_integration_mock.py`
- **Explanation**: The mock test was trying to import HA dependencies

### **"Permission denied /dev/ttyUSB0"**
```bash
# Quick fix
sudo chmod 666 /dev/ttyUSB0

# Permanent fix  
sudo usermod -a -G dialout $USER
# Then logout and login again
```

### **"USB device not found"**
```bash
# Check if device exists
ls -la /dev/ttyUSB*

# Check USB connections
lsusb
dmesg | grep ttyUSB
```

### **Hardware test fails but reference script works**
```bash
# Compare outputs
python3 read_ultralite_pyserial.py --debug --window 2.5
./test_hardware.py

# Check for differences in error messages
```

## ✅ **Expected Test Results**

### `./test_standalone.py` - Should Always Pass
```
🎉 Integration logic is working correctly!
📊 Test Results Summary:
  ✅ PASS M-Bus Data Parsing  
  ✅ PASS Sensor Definitions
  ✅ PASS Device Information
  ✅ PASS Error Handling
```

### `./test_hardware.py` - Should Pass with Hardware
```
🎉 All hardware tests passed!
📊 Retrieved X data points:
   📈 energy_total: 11570.0 kWh
   📈 volume_total: 355.04 m³
   📈 flow_temperature: 40.2 °C
   ...
```

### Home Assistant Integration - Should Show
- Device: "Itron UltraLite PRO" 
- 11 sensor entities
- All sensors show current values
- Services: `ultralite_pro.update_sensors` available

This gives you a clear testing strategy that works regardless of your environment! 🎯
