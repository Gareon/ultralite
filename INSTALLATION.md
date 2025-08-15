# Installation Guide for UltraLite PRO Home Assistant Integration

## Quick Installation Steps

### 1. Copy Integration Files

Copy the entire `custom_components/ultralite_pro` directory to your Home Assistant configuration directory:

```bash
# If using Home Assistant OS or Supervised
cp -r custom_components/ultralite_pro /config/custom_components/

# If using Home Assistant Core
cp -r custom_components/ultralite_pro ~/.homeassistant/custom_components/
```

### 2. Set USB Device Permissions

Ensure Home Assistant can access your USB IR device:

```bash
# Check current permissions
ls -la /dev/ttyUSB*

# Add homeassistant user to dialout group (if needed)
sudo usermod -a -G dialout homeassistant

# Or set specific permissions
sudo chmod 666 /dev/ttyUSB0
```

### 3. Restart Home Assistant

Restart Home Assistant to load the new integration:

```bash
# Home Assistant OS/Supervised
ha core restart

# Home Assistant Core
sudo systemctl restart home-assistant@homeassistant
```

### 4. Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "UltraLite PRO"
4. Follow the setup wizard:
   - **USB Device Path**: `/dev/ttyUSB0` (or your device path)
   - **Update Interval**: `60` seconds (recommended)
   - **Primary Address**: `0xFE` (default broadcast address)

### 5. Verify Installation

After setup, you should see:
- A new device: "Itron UltraLite PRO"
- 11 sensor entities (energy, volume, temperatures, etc.)
- Manual update service: `ultralite_pro.update_sensors`

## Configuration Options

### Update Intervals
- **10-3600 seconds**: Automatic polling
- **0**: Disable automatic updates (manual only)

### USB Device Paths
Common paths:
- `/dev/ttyUSB0` (most common)
- `/dev/ttyUSB1`
- `/dev/ttyACM0` (some devices)
- `/dev/serial/by-id/...` (persistent naming)

### Primary Address
- **0xFE**: Broadcast (default, works with most meters)
- **0x00-0xFF**: Specific meter address if configured

## Troubleshooting

### Common Issues

**"USB device not found"**
- Check cable connections
- Verify device path: `ls -la /dev/ttyUSB*`
- Try different USB ports

**"Permission denied"**
- Add user to dialout group: `sudo usermod -a -G dialout homeassistant`
- Check device permissions: `ls -la /dev/ttyUSB0`

**"Target device not responding"**
- Check IR alignment between reader and meter
- Verify meter is powered and not in sleep mode
- Try different primary address values

**Sensors show "Unavailable"**
- Check Home Assistant logs for error details
- Verify USB device is still connected
- Manual update: call `ultralite_pro.update_sensors` service

### Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.ultralite_pro: debug
```

## Hardware Setup

### IR Reader Positioning
1. Align IR reader with the optical interface on the meter
2. Ensure good contact and stable mounting
3. Avoid direct sunlight on the IR interface

### Meter Configuration
Most UltraLite PRO meters work with default settings:
- Primary address: 0xFE (broadcast)
- M-Bus protocol enabled
- Optical interface active

## Energy Dashboard Integration

### Add to Energy Dashboard
1. Go to **Settings** → **Dashboards** → **Energy**
2. Add "Total Energy" sensor as energy source
3. Optionally add "Thermal Power" for power monitoring

### Utility Meter (Optional)
For daily/monthly tracking:

```yaml
utility_meter:
  daily_energy:
    source: sensor.ultralite_pro_total_energy
    cycle: daily
  monthly_energy:
    source: sensor.ultralite_pro_total_energy
    cycle: monthly
```

## Services

### Manual Update
Force immediate sensor update:

```yaml
service: ultralite_pro.update_sensors
```

### Update Specific Device
```yaml
service: ultralite_pro.update_sensors
data:
  device_id: "your-device-id-here"
```

## File Structure

Your Home Assistant should have:
```
config/
├── custom_components/
│   └── ultralite_pro/
│       ├── __init__.py
│       ├── manifest.json
│       ├── const.py
│       ├── config_flow.py
│       ├── coordinator.py
│       ├── sensor.py
│       ├── mbus.py
│       ├── services.yaml
│       └── translations/
│           └── en.json
└── ...
```

## Next Steps

After successful installation:

1. **Monitor**: Watch sensor values to ensure proper operation
2. **Automate**: Create automations based on energy/temperature data
3. **Dashboard**: Add sensors to your energy dashboard
4. **Alert**: Set up notifications for unusual consumption patterns

## Support

For issues or questions:
1. Check Home Assistant logs first
2. Verify hardware connections
3. Test with the original Python script to isolate hardware issues
4. Review this documentation for troubleshooting steps
