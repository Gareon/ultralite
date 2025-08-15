#!/usr/bin/env python3
"""
Hardware-in-the-loop test for UltraLite PRO integration.
This tests the integration with your actual hardware setup.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_with_hardware():
    """Test integration components with real hardware."""
    print("🔌 UltraLite PRO Hardware Integration Test")
    print("=" * 50)
    print("This test requires your USB IR device to be connected")
    print()
    
    # Import after path setup
    try:
        from custom_components.ultralite_pro.mbus import MBusReader
        print("✅ Successfully imported MBusReader")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("This is expected outside of Home Assistant environment")
        return False
    
    # Test parameters (adjust as needed)
    usb_path = "/dev/ttyUSB0"  # Change this to your device
    primary_address = 0xFE
    
    print(f"📍 Testing with USB device: {usb_path}")
    print(f"📍 Primary address: 0x{primary_address:02X}")
    print()
    
    reader = MBusReader(usb_path, primary_address)
    
    try:
        print("🔗 Testing connection...")
        connected = await reader.connect()
        if not connected:
            print("❌ Failed to connect to USB device")
            print("💡 Check:")
            print("   - USB device path is correct")
            print("   - Device permissions (try: sudo chmod 666 /dev/ttyUSB0)")
            print("   - USB cable and IR alignment")
            return False
        
        print("✅ Connection successful")
        
        print("\n📡 Reading data from meter...")
        data = await reader.read_data()
        
        print("✅ Data read successful!")
        print(f"📊 Retrieved {len(data)} data points:")
        print()
        
        # Display the data in a nice format
        sensor_order = [
            "serial_number", "device_id", "manufacturer", "version",
            "energy_total", "volume_total", "volume_flow",
            "flow_temperature", "return_temperature", "delta_temperature",
            "thermal_power", "operating_time_days",
            "firmware_version", "software_version"
        ]
        
        for key in sensor_order:
            if key in data:
                value = data[key]
                if isinstance(value, dict) and 'value' in value:
                    unit = f" {value['unit']}" if value['unit'] else ""
                    print(f"   📈 {key}: {value['value']}{unit}")
                else:
                    print(f"   ℹ️  {key}: {value}")
        
        # Show any additional data not in the ordered list
        remaining_keys = set(data.keys()) - set(sensor_order)
        if remaining_keys:
            print("\n   Additional data:")
            for key in remaining_keys:
                value = data[key]
                print(f"   🔹 {key}: {value}")
        
        print("\n🎉 Hardware test completed successfully!")
        return True
        
    except PermissionError:
        print("❌ Permission denied accessing USB device")
        print("💡 Try: sudo chmod 666 /dev/ttyUSB0")
        print("   Or: sudo usermod -a -G dialout $USER (then logout/login)")
        return False
        
    except FileNotFoundError:
        print("❌ USB device not found")
        print("💡 Check if device is connected:")
        print("   ls -la /dev/ttyUSB*")
        return False
        
    except Exception as e:
        print(f"❌ Error during hardware test: {e}")
        print(f"   Error type: {type(e).__name__}")
        logger.exception("Full error details:")
        return False
        
    finally:
        reader.disconnect()
        print("\n🔌 Disconnected from device")

async def test_multiple_reads():
    """Test multiple consecutive reads to verify stability."""
    print("\n🔄 Testing Multiple Consecutive Reads")
    print("-" * 40)
    
    from custom_components.ultralite_pro.mbus import MBusReader
    
    usb_path = "/dev/ttyUSB0"
    reader = MBusReader(usb_path, 0xFE)
    
    success_count = 0
    total_reads = 3
    
    for i in range(total_reads):
        try:
            print(f"📡 Read {i+1}/{total_reads}...")
            data = await reader.read_data()
            
            # Check for key values
            energy = data.get("energy_total", {}).get("value")
            temp = data.get("flow_temperature", {}).get("value")
            
            print(f"   ✅ Energy: {energy} kWh, Flow temp: {temp}°C")
            success_count += 1
            
            # Small delay between reads
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Read {i+1} failed: {e}")
    
    reader.disconnect()
    
    print(f"\n📊 Results: {success_count}/{total_reads} successful reads")
    return success_count == total_reads

def check_usb_permissions():
    """Check USB device permissions and provide guidance."""
    print("🔍 Checking USB Device Setup")
    print("-" * 30)
    
    import os
    import stat
    
    # Common USB device paths
    usb_paths = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"]
    
    found_devices = []
    for path in usb_paths:
        if os.path.exists(path):
            found_devices.append(path)
            
            # Check permissions
            file_stat = os.stat(path)
            mode = stat.filemode(file_stat.st_mode)
            
            print(f"✅ Found: {path}")
            print(f"   Permissions: {mode}")
            print(f"   Owner: {file_stat.st_uid}, Group: {file_stat.st_gid}")
            
            # Check if readable/writable
            readable = os.access(path, os.R_OK)
            writable = os.access(path, os.W_OK)
            
            print(f"   Readable: {'✅' if readable else '❌'}")
            print(f"   Writable: {'✅' if writable else '❌'}")
            
            if not (readable and writable):
                print(f"   💡 Fix with: sudo chmod 666 {path}")
            print()
    
    if not found_devices:
        print("❌ No USB devices found")
        print("💡 Check if your USB IR device is connected")
        print("   Try: lsusb")
        print("   Try: dmesg | grep tty")
    
    return len(found_devices) > 0

async def main():
    """Run hardware tests."""
    print("🔌 UltraLite PRO Hardware Testing Suite")
    print("=" * 60)
    
    # First check USB setup
    if not check_usb_permissions():
        print("⚠️  Please connect your USB IR device and try again")
        return 1
    
    # Test with hardware
    success = await test_with_hardware()
    
    if success:
        # If basic test passed, try multiple reads
        stability_success = await test_multiple_reads()
        
        if stability_success:
            print("\n🎉 All hardware tests passed!")
            print("💡 Your setup is ready for Home Assistant integration")
            print()
            print("Next steps:")
            print("1. Run setup script: ./setup_ha_dev.sh")
            print("2. Start HA: cd ha_dev && docker-compose up -d")
            print("3. Open: http://localhost:8123")
            print("4. Add integration: Settings > Devices & Services > Add Integration")
            return 0
        else:
            print("\n⚠️  Basic test passed but stability test failed")
            print("💡 Check USB connection and try again")
            return 1
    else:
        print("\n❌ Hardware test failed")
        print("💡 Fix the issues above and try again")
        return 1

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
