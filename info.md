# UltraLite PRO Energy Meter

A Home Assistant custom integration for the **Itron/Integral-V UltraLite PRO** energy meter that communicates via USB IR interface using the M-Bus protocol.

> [!CAUTION]
> Almost the whole project, including the documentation, is created using GitHub Copilot. I didn't review it thoroughly, so there might be inaccuracies or errors. Please double-check the information and adapt it to your needs.

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

After installation via HACS:

1. Restart Home Assistant
2. Go to **Settings** → **Devices & Services** → **Add Integration**
3. Search for "UltraLite PRO" and follow the setup wizard
4. Configure your USB IR interface device path (e.g., `/dev/ttyUSB0`)

## Configuration

- **Device Path**: Path to your USB IR interface (usually `/dev/ttyUSB0`)
- **Update Interval**: How often to poll the meter (default: 300 seconds)
- **Address**: M-Bus address of your meter (default: 1)

For detailed setup instructions, see the [full README](https://github.com/Gareon/ultralite/blob/main/README.md).
