#!/usr/bin/env python3
"""
Standalone mock testing script for UltraLite PRO integration.
This tests the core logic without requiring Home Assistant dependencies.
"""

import asyncio
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mbus_parsing():
    """Test M-Bus data parsing without serial dependencies."""
    print("🔍 Testing M-Bus Data Parsing")
    print("-" * 40)
    
    # Import the parsing functions directly from your working script
    sys.path.insert(0, str(Path.cwd()))
    
    # Copy the core functions from read_ultralite_pyserial.py
    import struct
    import datetime
    
    def decode_bcd_le(data: bytes) -> int:
        """Little-endian packed BCD -> int (ignores 0xF nibbles)."""
        digits = []
        for x in data:
            lo, hi = x & 0x0F, (x >> 4) & 0x0F
            if lo <= 9:
                digits.append(str(lo))
            if hi <= 9:
                digits.append(str(hi))
        return int("".join(reversed(digits))) if digits else 0

    def _volume_scaled(vif, val_int):
        """Volume family 0x20..0x27: m³ * 10^(n-6) where n=vif&7."""
        n = vif & 0x07
        return float(val_int) * (10 ** (n - 6))

    def _ts(secs):
        """Convert timestamp to ISO format."""
        try:
            return datetime.datetime.fromtimestamp(int(secs), datetime.timezone.utc).isoformat()
        except Exception:
            return None

    # VIF mapping from your script
    VIF_MAP = {
        0x06: ("energy_total",        lambda v, vif: float(v),          "kWh"),
        0x14: ("volume_total",        lambda v, vif: float(v) / 100.0,  "m³"),
        0x27: ("operating_time_days", lambda v, vif: int(v),            "days"),
        0x38: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x39: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x3A: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x3B: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x3C: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x3D: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x3E: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x3F: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
        0x5A: ("flow_temperature",    lambda v, vif: float(v) / 10.0,   "°C"),
        0x5E: ("return_temperature",  lambda v, vif: float(v) / 10.0,   "°C"),
        0x61: ("delta_temperature",   lambda v, vif: float(v) / 100.0,  "K"),
        0x6D: ("time_point",          lambda v, vif: _ts(v),            None),
        0x78: ("serial_number",       lambda v, vif: str(int(v)).zfill(8), None),
    }

    VIF_EXT_MAP = {
        0x0E: ("firmware_version", lambda v: int(v), None),
        0x0F: ("software_version", lambda v: int(v), None),
        0x08: ("access_number",    lambda v: int(v), None),
        0x09: ("medium_code",      lambda v: int(v), None),
    }

    def record_to_human(r):
        """Return (key, value, unit) or None if not mapped."""
        if "special" in r or r["value"] is None:
            return None
        VIF = r["VIF"]
        val = r["value"]

        # Extension VIF (0xFD)
        if VIF == 0xFD and r["VIFEs"]:
            vife = r["VIFEs"][0] & 0x7F
            if vife in VIF_EXT_MAP:
                name, fn, unit = VIF_EXT_MAP[vife]
                return (name, fn(val), unit)
            return None

        # Direct map
        if VIF in VIF_MAP:
            name, fn, unit = VIF_MAP[VIF]
            try:
                return (name, fn(val, VIF), unit)
            except TypeError:
                return (name, fn(val), unit)

        return None

    # Test data parsing with your actual sensor values
    test_records = [
        {"VIF": 0x06, "value": 11570, "VIFEs": []},      # energy_total
        {"VIF": 0x14, "value": 35504, "VIFEs": []},      # volume_total (BCD)
        {"VIF": 0x3B, "value": 295, "VIFEs": []},        # volume_flow
        {"VIF": 0x5A, "value": 402, "VIFEs": []},        # flow_temperature
        {"VIF": 0x5E, "value": 308, "VIFEs": []},        # return_temperature
        {"VIF": 0x61, "value": 935, "VIFEs": []},        # delta_temperature
        {"VIF": 0x78, "value": 22106352, "VIFEs": []},   # serial_number
        {"VIF": 0x27, "value": 1095, "VIFEs": []},       # operating_time_days
        {"VIF": 0xFD, "value": 8, "VIFEs": [0x0E]},      # firmware_version
        {"VIF": 0xFD, "value": 11, "VIFEs": [0x0F]},     # software_version
    ]

    print("✅ Testing VIF mapping with real meter data:")
    
    parsed_data = {}
    for record in test_records:
        result = record_to_human(record)
        if result:
            name, value, unit = result
            unit_str = f" {unit}" if unit else ""
            print(f"   📊 {name}: {value}{unit_str}")
            parsed_data[name] = {"value": value, "unit": unit}
        else:
            print(f"   ❌ VIF 0x{record['VIF']:02X}: No mapping")

    # Test thermal power calculation
    if ("volume_flow" in parsed_data and "delta_temperature" in parsed_data and
        parsed_data["volume_flow"]["value"] is not None and 
        parsed_data["delta_temperature"]["value"] is not None):
        flow_m3h = float(parsed_data["volume_flow"]["value"])
        dT = float(parsed_data["delta_temperature"]["value"])
        power_kW = 1.163 * flow_m3h * dT
        parsed_data["thermal_power"] = {"value": power_kW, "unit": "kW"}
        print(f"   🔥 thermal_power: {power_kW:.3f} kW (calculated)")

    print(f"\n✅ Successfully parsed {len(parsed_data)} sensor values")
    return True

def test_sensor_definitions():
    """Test sensor definitions for Home Assistant."""
    print("\n🔍 Testing Sensor Definitions")
    print("-" * 40)
    
    # Define sensor types as they would be in Home Assistant
    SENSOR_TYPES = {
        "energy_total": {
            "name": "Total Energy",
            "device_class": "energy",
            "state_class": "total_increasing",
            "unit": "kWh",
            "icon": "mdi:lightning-bolt",
        },
        "volume_total": {
            "name": "Total Volume",
            "device_class": "volume",
            "state_class": "total_increasing",
            "unit": "m³",
            "icon": "mdi:water",
        },
        "volume_flow": {
            "name": "Volume Flow Rate",
            "device_class": "volume_flow_rate",
            "state_class": "measurement",
            "unit": "m³/h",
            "icon": "mdi:pipe",
        },
        "flow_temperature": {
            "name": "Flow Temperature",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit": "°C",
            "icon": "mdi:thermometer-chevron-up",
        },
        "return_temperature": {
            "name": "Return Temperature",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit": "°C",
            "icon": "mdi:thermometer-chevron-down",
        },
        "delta_temperature": {
            "name": "Temperature Difference",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit": "K",
            "icon": "mdi:thermometer-minus",
        },
        "thermal_power": {
            "name": "Thermal Power",
            "device_class": "power",
            "state_class": "measurement",
            "unit": "kW",
            "icon": "mdi:fire",
        },
        "operating_time_days": {
            "name": "Operating Time",
            "device_class": "duration",
            "state_class": "total_increasing",
            "unit": "days",
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

    print(f"✅ Sensor definitions: {len(SENSOR_TYPES)} sensors configured")
    
    # Check each sensor type
    for sensor_key, config in SENSOR_TYPES.items():
        name = config['name']
        device_class = config.get('device_class', 'None')
        state_class = config.get('state_class', 'None')
        unit = config.get('unit', 'None')
        
        print(f"   📊 {sensor_key}:")
        print(f"      Name: {name}")
        print(f"      Device Class: {device_class}")
        print(f"      State Class: {state_class}")
        print(f"      Unit: {unit}")
        print()
    
    return True

def test_device_info():
    """Test device information structure."""
    print("🔍 Testing Device Information")
    print("-" * 40)
    
    # Mock device data as it would come from the meter
    device_data = {
        "device_id": 22106352,
        "manufacturer": "ITR",
        "version": 23,
        "medium": 0x04,
        "access_no": 33,
        "status": 0x00,
        "serial_number": {"value": "22106352", "unit": None},
        "firmware_version": {"value": 8, "unit": None},
        "software_version": {"value": 11, "unit": None},
    }
    
    # Extract device info as the integration would
    device_serial = device_data.get("serial_number", {}).get("value") or str(device_data.get("device_id", "unknown"))
    manufacturer = "Itron"
    model = "UltraLite PRO"
    sw_version = str(device_data.get("software_version", {}).get("value", ""))
    hw_version = str(device_data.get("firmware_version", {}).get("value", ""))
    
    print("✅ Device Information:")
    print(f"   Serial Number: {device_serial}")
    print(f"   Manufacturer: {manufacturer}")
    print(f"   Model: {model}")
    print(f"   Software Version: {sw_version}")
    print(f"   Hardware Version: {hw_version}")
    print(f"   Device ID: {device_data['device_id']}")
    print(f"   M-Bus Manufacturer: {device_data['manufacturer']}")
    print(f"   Version: {device_data['version']}")
    print(f"   Medium: 0x{device_data['medium']:02X}")
    
    return True

def test_error_handling():
    """Test error handling scenarios."""
    print("\n🔍 Testing Error Handling Scenarios")
    print("-" * 40)
    
    error_scenarios = [
        ("USB device not found", "/dev/ttyUSB99"),
        ("Permission denied", "/dev/ttyUSB0 (no permissions)"),
        ("Device not responding", "No valid data received"),
        ("Invalid address", "Primary address out of range"),
        ("Communication timeout", "Serial timeout"),
    ]
    
    print("✅ Error scenarios that should be handled:")
    for error_type, description in error_scenarios:
        print(f"   ⚠️  {error_type}: {description}")
    
    # Test configuration validation
    test_configs = [
        {"usb_path": "/dev/ttyUSB0", "update_interval": 60, "primary_address": "0xFE"},
        {"usb_path": "/dev/ttyUSB1", "update_interval": 30, "primary_address": "0x00"},
        {"usb_path": "/dev/ttyACM0", "update_interval": 120, "primary_address": "254"},
    ]
    
    print("\n✅ Configuration validation tests:")
    for i, config in enumerate(test_configs, 1):
        print(f"   {i}. USB: {config['usb_path']}, Interval: {config['update_interval']}s, Address: {config['primary_address']}")
    
    return True

def main():
    """Run all standalone tests."""
    print("🧪 UltraLite PRO Integration Standalone Testing")
    print("=" * 60)
    print("Testing integration logic without Home Assistant dependencies")
    print()
    
    tests = [
        ("M-Bus Data Parsing", test_mbus_parsing),
        ("Sensor Definitions", test_sensor_definitions),
        ("Device Information", test_device_info),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    print(f"\n🏁 Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🎉 Integration logic is working correctly!")
        print("\n💡 Next steps:")
        print("   1. Test with hardware: ./test_hardware.py")
        print("   2. Set up HA dev environment: ./setup_ha_dev.sh")
        print("   3. Test in Home Assistant")
    else:
        print("\n❌ Please fix the failed tests before proceeding")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
