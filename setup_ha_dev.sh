#!/bin/bash
# setup_ha_dev.sh - Set up Home Assistant development environment

echo "🏠 Setting up Home Assistant Development Environment"
echo "=================================================="

# Create development directory structure
mkdir -p ha_dev/{config,custom_components}

# Copy our integration
echo "📁 Copying UltraLite PRO integration..."
cp -r custom_components/ultralite_pro ha_dev/custom_components/

# Create basic Home Assistant configuration
cat > ha_dev/config/configuration.yaml << 'EOF'
# Home Assistant Development Configuration
homeassistant:
  name: "HA Dev"
  latitude: 52.5
  longitude: 13.4
  elevation: 43
  unit_system: metric
  time_zone: "Europe/Berlin"
  
default_config:

# Enable logging
logger:
  default: info
  logs:
    custom_components.ultralite_pro: debug

# Enable the frontend
frontend:

# Enable discovery of devices
discovery:

# Enable energy dashboard
energy:
EOF

# Create docker-compose for development
cat > ha_dev/docker-compose.yml << 'EOF'
services:
  homeassistant:
    container_name: ha_dev
    image: ghcr.io/home-assistant/home-assistant:stable
    volumes:
      - ./config:/config
      - ../custom_components/ultralite_pro:/config/custom_components/ultralite_pro:ro
      - /etc/localtime:/etc/localtime:ro
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    group_add:
      - dialout
    restart: unless-stopped
    # privileged: true
    network_mode: host
    environment:
      - TZ=Europe/Berlin
EOF

echo "✅ Development environment created in ha_dev/"
echo ""
echo "🚀 To start Home Assistant:"
echo "   cd ha_dev && docker-compose up -d"
echo ""
echo "🌐 Access at: http://localhost:8123"
echo "📊 Check logs: docker-compose logs -f homeassistant"
