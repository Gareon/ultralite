# UltraLite PRO Energy Meter Integration for Home Assistant

A Home Assistant custom integration for the **Itron/Integral-V UltraLite PRO** energy meter that communicates via USB IR interface using the M-Bus protocol.

## Features

- 📊 **Real-time Energy Monitoring**: Track total energy consumption, volume flow, temperatures, and thermal power
- 🔌 **USB IR Interface**: Connects via standard USB IR reader (typically `/dev/ttyUSBx`)
- 🏠 **Native Home Assistant Integration**: Full integration with HA device registry, entities, and services
- 🔄 **Automatic Updates**: Configurable polling intervals with error handling and recovery
- 🛠️ **Manual Updates**: Service for on-demand sensor updates
- 🚨 **Robust Error Handling**: Graceful handling of device disconnections and communication errors
- 📈 **Energy Dashboard Compatible**: Sensors work with Home Assistant's Energy Dashboard

## Supported Sensors

The integration creates sensors for all available meter data points:

### Energy & Volume
- **Total Energy** (kWh) - Cumulative energy consumption
- **Total Volume** (m³) - Cumulative volume 
- **Volume Flow Rate** (m³/h) - Current flow rate

### Temperature Monitoring  
- **Flow Temperature** (°C) - Supply temperature
- **Return Temperature** (°C) - Return temperature
- **Temperature Difference** (K) - Delta temperature

### Calculated Values
- **Thermal Power** (kW) - Calculated as `1.163 × flow_rate × delta_temp`

### Device Information
- **Operating Time** (days) - Device operational time
- **Serial Number** - Device identifier
- **Firmware Version** - Device firmware version
- **Software Version** - Device software version

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Install "UltraLite PRO Energy Meter" from HACS
3. Restart Home Assistant
4. Go to **Settings** → **Devices & Services** → **Add Integration**
5. Search for "UltraLite PRO" and follow the setup wizard

### Manual Installation

1. Copy the `custom_components/ultralite_pro` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the integration via the UI

## Configuration

The integration is configured through the Home Assistant UI:

### Basic Settings
- **USB Device Path**: Path to your USB IR device (default: `/dev/ttyUSB0`)
- **Update Interval**: How often to poll the meter in seconds (10-3600, or 0 to disable automatic updates)
- **Primary Address**: M-Bus primary address in hex format (default: `0xFE`)

### USB Device Setup

Most USB IR readers appear as `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc. To find your device:

```bash
# List USB serial devices
ls -la /dev/ttyUSB*

# Check device permissions
ls -la /dev/ttyUSB0
```

Ensure Home Assistant has permission to access the USB device. You may need to add the `homeassistant` user to the `dialout` group:

```bash
sudo usermod -a -G dialout homeassistant
```

## Hardware Requirements

### Supported Devices
- **Meter**: Itron/Integral-V UltraLite PRO energy meter
- **Interface**: USB IR reader compatible with M-Bus protocol
- **Connection**: IR optical interface on the meter

### Communication Protocol
- **Protocol**: M-Bus over serial
- **Wakeup**: 0x55 @ 2400 baud 8N1
- **Commands**: SND_NKE + REQ_UD2 @ 2400 baud 8E1
- **Primary Address**: Configurable (default 0xFE for broadcast)

## Usage

### Automatic Updates
Once configured, sensors update automatically based on your chosen interval. The integration handles:
- Device disconnections with automatic reconnection attempts
- Communication timeouts with exponential backoff retry
- Error states with clear status indicators

### Manual Updates
Use the `ultralite_pro.update_sensors` service for immediate updates:

```yaml
# Update all UltraLite PRO devices
service: ultralite_pro.update_sensors

# Update specific device
service: ultralite_pro.update_sensors
data:
  device_id: "your-device-id"
```

### Energy Dashboard
Add the **Total Energy** sensor to Home Assistant's Energy Dashboard:
1. Go to **Settings** → **Dashboards** → **Energy**
2. Add **Total Energy** sensor as an energy source
3. Optionally add **Thermal Power** for real-time power monitoring

## Error Handling

The integration provides clear error messages for common issues:

- **USB device not found**: Check device path and connections
- **Permission denied**: Verify Home Assistant has USB device access
- **Target device not responding**: Check IR alignment and meter status
- **Device response not understood**: Communication protocol issues

Sensors become "unavailable" during communication problems but preserve their last known values. Total/cumulative values (energy, volume) are maintained across disconnections.

## Troubleshooting

### Common Issues

**Device not found at startup**
- Verify USB device path in configuration
- Check USB cable and IR reader connections
- Ensure proper permissions on device file

**Intermittent communication failures**
- Check IR alignment between reader and meter
- Verify meter is not in sleep mode
- Ensure stable USB connection

**Permission denied errors**
- Add `homeassistant` user to `dialout` group
- Check SELinux/AppArmor policies if applicable
- Verify device file permissions

### Debug Logging

Enable debug logging to troubleshoot communication issues:

```yaml
logger:
  default: info
  logs:
    custom_components.ultralite_pro: debug
```

## Technical Details

### M-Bus Communication
The integration uses the standard M-Bus protocol with specific timing requirements:
1. **Wakeup sequence**: Sends 0x55 bytes for 2.2 seconds at 2400 8N1
2. **Command sequence**: SND_NKE followed by REQ_UD2 at 2400 8E1
3. **Response parsing**: Validates checksums and extracts structured data

### Data Processing
- **VIF Mapping**: Uses Variable Information Field codes to identify data types
- **Unit Conversion**: Automatic scaling and unit conversion (BCD, scaling factors)
- **Calculated Values**: Thermal power computed using standard heat meter formula

### Device Registry
All sensors are grouped under a single device in Home Assistant with:
- Device identifiers based on meter serial number
- Manufacturer: Itron
- Model: UltraLite PRO
- Software/firmware version information

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Based on the M-Bus communication protocol specification
- Inspired by the Home Assistant community's energy monitoring efforts
- Special thanks to the PySerial library maintainers
