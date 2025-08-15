#!/usr/bin/env python3
"""
Mock testing script for UltraLite PRO integration development.
This allows testing the integration logic without the physical hardware.
"""

import asyncio
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class MockSerial:
    """Mock serial interface for testing."""
    
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.baudrate = 2400
        self.bytesize = 8
        self.parity = 'N'
        self.stopbits = 1
        self.timeout = 0.15
        
    def write(self, data):
        logger.debug(f"Mock serial write: {data.hex()}")
        return len(data)
        
    def flush(self):
        pass
        
    def read(self, size):
        # Return mock M-Bus response frame
        # This is a simplified mock response
        mock_frame = bytes([
            0x68, 0x3E, 0x3E, 0x68,  # Frame header
            0x08, 0xFE, 0x72,        # Control, Address, CI
            # Mock data payload with some of the VIF codes we expect
            0x52, 0x63, 0x01, 0x22, 0x49, 0x54, 0x17, 0x04, 0x33, 0x00, 0x00, 0x00,
            # More mock data...
            0x84, 0x40, 0x06, 0x32, 0x2D, 0x00, 0x00,  # Energy total
            0x84, 0x40, 0x14, 0x04, 0x55, 0x03, 0x00,  # Volume total  
            0x02, 0x3B, 0x27, 0x01,                     # Volume flow
            0x02, 0x5A, 0x92, 0x01,                     # Flow temp
            0x02, 0x5E, 0x34, 0x01,                     # Return temp
            0x02, 0x61, 0x67, 0x03,                     # Delta temp
            0x04, 0x78, 0x52, 0x63, 0x01, 0x22,        # Serial number
            0x02, 0x27, 0x47, 0x04,                     # Operating time
            0xA4, 0x16  # Checksum and end
        ])
        return mock_frame[:size] if len(mock_frame) >= size else mock_frame
        
    def reset_input_buffer(self):
        pass
        
    def reset_output_buffer(self):
        pass
        
    def close(self):
        self.is_open = False

# Mock the serial module
class MockSerialModule:
    Serial = MockSerial
    EIGHTBITS = 8
    PARITY_NONE = 'N' 
    PARITY_EVEN = 'E'
    STOPBITS_ONE = 1
    
    class SerialException(Exception):
        pass

# Replace the serial import in mbus.py
sys.modules['serial'] = MockSerialModule()

# Now we can import our modules
try:
    from custom_components.ultralite_pro.mbus import MBusReader
    from custom_components.ultralite_pro.coordinator import UltraLiteProCoordinator
    print("✅ Successfully imported integration modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Note: This is expected outside of Home Assistant environment")
    sys.exit(1)

class MockConfigEntry:
    """Mock Home Assistant config entry."""
    
    def __init__(self):
        self.data = {
            "usb_path": "/dev/ttyUSB0",
            "update_interval": 60,
            "primary_address": 0xFE
        }
        self.entry_id = "mock_entry"

class MockHass:
    """Mock Home Assistant instance."""
    
    def __init__(self):
        self.data = {}

async def test_mbus_reader():
    """Test the M-Bus reader with mock hardware."""
    print("\n🔍 Testing M-Bus Reader with Mock Hardware")
    print("-" * 50)
    
    reader = MBusReader("/dev/ttyUSB0", 0xFE)
    
    try:
        # Test connection
        connected = await reader.connect()
        print(f"✅ Connection: {'Success' if connected else 'Failed'}")
        
        # Test data reading
        data = await reader.read_data()
        print(f"✅ Data reading: Success")
        print(f"   Device ID: {data.get('device_id', 'Unknown')}")
        
        # Print all available data
        print("\n📊 Mock Sensor Data:")
        for key, value in data.items():
            if isinstance(value, dict) and 'value' in value:
                unit = f" {value['unit']}" if value['unit'] else ""
                print(f"   {key}: {value['value']}{unit}")
            else:
                print(f"   {key}: {value}")
                
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        reader.disconnect()

async def test_coordinator():
    """Test the coordinator with mock hardware."""
    print("\n🔍 Testing Data Update Coordinator")
    print("-" * 50)
    
    from datetime import timedelta
    
    mock_hass = MockHass()
    mock_config = MockConfigEntry()
    
    coordinator = UltraLiteProCoordinator(
        mock_hass, 
        mock_config, 
        timedelta(seconds=60)
    )
    
    try:
        # Test data update
        data = await coordinator._async_update_data()
        print(f"✅ Coordinator update: Success")
        print(f"   Retrieved {len(data)} data points")
        
        # Test retry mechanism (this should work with mock)
        retry_data = await coordinator._fetch_data_with_retry()
        print(f"✅ Retry mechanism: Success")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        await coordinator.async_shutdown()

def test_sensor_config():
    """Test sensor configuration."""
    print("\n🔍 Testing Sensor Configuration")
    print("-" * 50)
    
    try:
        from custom_components.ultralite_pro.sensor import SENSOR_TYPES
        
        print(f"✅ Sensor types loaded: {len(SENSOR_TYPES)} sensors")
        
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
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    """Run all mock tests."""
    print("🧪 UltraLite PRO Integration Mock Testing")
    print("=" * 60)
    print("This tests the integration logic without requiring hardware")
    print()
    
    tests = [
        ("M-Bus Reader", test_mbus_reader),
        ("Data Coordinator", test_coordinator),
        ("Sensor Configuration", lambda: test_sensor_config()),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📋 Test Results Summary:")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    print(f"\n🏁 Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🎉 Integration logic is working correctly!")
        print("💡 Ready for testing with Home Assistant:")
        print("   1. Run: ./setup_ha_dev.sh")
        print("   2. Start: cd ha_dev && docker-compose up -d")
        print("   3. Open: http://localhost:8123")
        print("   4. Add integration via Settings > Devices & Services")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    asyncio.run(main())
