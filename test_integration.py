#!/usr/bin/env python3
"""
Test script to verify UltraLite PRO integration structure and basic functionality.
This script can be run to check if all files are present and importable.
"""

import sys
import os
from pathlib import Path

def test_integration_structure():
    """Test that all required files exist."""
    base_path = Path("custom_components/ultralite_pro")
    
    required_files = [
        "__init__.py",
        "manifest.json",
        "const.py",
        "config_flow.py",
        "coordinator.py", 
        "sensor.py",
        "mbus.py",
        "services.yaml",
        "translations/en.json"
    ]
    
    print("🔍 Checking integration file structure...")
    
    all_exist = True
    for file_path in required_files:
        full_path = base_path / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - MISSING")
            all_exist = False
    
    return all_exist

def test_imports():
    """Test that modules can be imported."""
    print("\n🔍 Testing Python imports...")
    
    # Add the custom_components directory to Python path
    sys.path.insert(0, str(Path.cwd()))
    
    modules_to_test = [
        "custom_components.ultralite_pro.const",
        "custom_components.ultralite_pro.mbus", 
        "custom_components.ultralite_pro.config_flow",
        "custom_components.ultralite_pro.coordinator",
        "custom_components.ultralite_pro.sensor",
    ]
    
    all_imported = True
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
        except ImportError as e:
            print(f"❌ {module_name} - IMPORT ERROR: {e}")
            all_imported = False
        except Exception as e:
            print(f"⚠️  {module_name} - OTHER ERROR: {e}")
    
    return all_imported

def test_manifest():
    """Test manifest.json structure."""
    print("\n🔍 Testing manifest.json...")
    
    import json
    
    try:
        with open("custom_components/ultralite_pro/manifest.json") as f:
            manifest = json.load(f)
        
        required_keys = ["domain", "name", "config_flow", "dependencies", "requirements", "version"]
        
        all_keys_present = True
        for key in required_keys:
            if key in manifest:
                print(f"✅ {key}: {manifest[key]}")
            else:
                print(f"❌ {key} - MISSING")
                all_keys_present = False
        
        return all_keys_present
        
    except Exception as e:
        print(f"❌ Error reading manifest.json: {e}")
        return False

def test_mbus_functionality():
    """Test basic M-Bus functionality without hardware."""
    print("\n🔍 Testing M-Bus module functionality...")
    
    try:
        from custom_components.ultralite_pro.mbus import (
            hexdump, decode_bcd_le, VIF_MAP, record_to_human
        )
        
        # Test hexdump
        test_data = b"\x68\x3E\x3E\x68\x08\xFE\x72"
        dump_lines = list(hexdump(test_data))
        print(f"✅ hexdump: {len(dump_lines)} lines generated")
        
        # Test BCD decode
        bcd_result = decode_bcd_le(b"\x52\x63\x01\x22")
        print(f"✅ decode_bcd_le: {bcd_result}")
        
        # Test VIF mapping
        print(f"✅ VIF_MAP: {len(VIF_MAP)} mappings loaded")
        
        # Test record parsing (mock record)
        mock_record = {
            "VIF": 0x06, 
            "value": 11570,
            "VIFEs": []
        }
        result = record_to_human(mock_record)
        if result:
            print(f"✅ record_to_human: {result}")
        else:
            print("❌ record_to_human: No result")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ M-Bus functionality test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 UltraLite PRO Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("File Structure", test_integration_structure),
        ("Python Imports", test_imports), 
        ("Manifest", test_manifest),
        ("M-Bus Functionality", test_mbus_functionality),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} {test_name}")
        if not passed:
            all_passed = False
    
    print(f"\n🏁 Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🎉 Integration is ready for Home Assistant!")
        print("💡 Next steps:")
        print("   1. Copy custom_components/ultralite_pro to your HA config")
        print("   2. Restart Home Assistant")
        print("   3. Add integration via Settings > Devices & Services")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
