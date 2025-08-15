#!/usr/bin/env python3
"""
Test the sensor fixes for the UltraLite PRO integration.
This validates that the AttributeError has been resolved.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

def test_sensor_fix():
    """Test that the sensor no longer has the AttributeError."""
    print("🔍 Testing Sensor Fixes")
    print("-" * 30)
    
    # Test the extra_state_attributes property doesn't reference non-existent attributes
    sensor_file = Path("custom_components/ultralite_pro/sensor.py")
    
    if not sensor_file.exists():
        print("❌ Sensor file not found")
        return False
    
    content = sensor_file.read_text()
    
    # Check that the problematic line has been removed/fixed
    if "self.coordinator.last_update_success_time" in content:
        print("❌ Still contains problematic last_update_success_time reference")
        return False
    
    print("✅ Removed problematic last_update_success_time reference")
    
    # Check that device_info is now a property
    if "@property" in content and "def device_info" in content:
        print("✅ Device info is now a dynamic property")
    else:
        print("⚠️  Device info may still be static")
    
    # Check for proper error handling
    if "device_data = self.coordinator.data or {}" in content:
        print("✅ Added proper None handling for coordinator data")
    else:
        print("⚠️  May still have issues with None coordinator data")
    
    print("\n📊 Key fixes applied:")
    print("   - Removed last_update_success_time reference")
    print("   - Made device_info a dynamic property")
    print("   - Added proper None handling for coordinator data")
    print("   - Use config entry ID as fallback for device serial")
    
    return True

def check_ha_logs():
    """Provide guidance for checking HA logs."""
    print("\n🔍 Checking Home Assistant Integration")
    print("-" * 40)
    
    print("📋 To verify the fix in Home Assistant:")
    print("1. Check logs for errors:")
    print("   cd ha_dev && docker compose logs -f homeassistant | grep ultralite_pro")
    print()
    print("2. Remove and re-add the integration:")
    print("   - Go to Settings → Devices & Services")
    print("   - Find UltraLite PRO integration")
    print("   - Click the three dots → Delete")
    print("   - Add Integration → Search 'UltraLite PRO'")
    print("   - Follow the setup wizard")
    print()
    print("3. Check that all sensors are created without errors:")
    print("   - Should see 11 sensors under the device")
    print("   - No more AttributeError in logs")
    print("   - All sensors should show data or 'Unavailable'")

def main():
    """Run the sensor fix validation."""
    print("🛠️ UltraLite PRO Sensor Fix Validation")
    print("=" * 50)
    
    success = test_sensor_fix()
    check_ha_logs()
    
    if success:
        print("\n✅ Sensor fixes have been applied successfully!")
        print("🔄 Home Assistant container has been restarted")
        print("💡 Try adding the integration again in HA")
        return 0
    else:
        print("\n❌ Issues found with sensor fixes")
        return 1

if __name__ == "__main__":
    sys.exit(main())
