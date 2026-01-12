#!/bin/bash
# Script to help configure ports 8091 and 8092 on macOS

echo "=========================================="
echo "Port Configuration Helper for macOS"
echo "=========================================="
echo ""
echo "This script will help you open ports 8091 and 8092"
echo "for your Bittensor miner and validator"
echo ""

PORTS=(8091 8092)

# Check if running on macOS
if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

# Check current firewall status
echo "📊 Checking current firewall status..."
FIREWALL_STATUS=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -i "enabled" || echo "disabled")

if [[ "$FIREWALL_STATUS" == *"enabled"* ]]; then
    echo "✅ Firewall is enabled"
else
    echo "⚠️  Firewall is disabled"
fi

echo ""
echo "🔍 Checking if ports are accessible..."

# Test if ports are listening
for port in "${PORTS[@]}"; do
    if lsof -i :$port > /dev/null 2>&1; then
        echo "✅ Port $port is in use (application is listening)"
        lsof -i :$port | head -2
    else
        echo "❌ Port $port is not in use (no application listening)"
    fi
done

echo ""
echo "=========================================="
echo "Configuration Options:"
echo "=========================================="
echo ""
echo "Option 1: macOS System Settings (Recommended)"
echo "  1. Open System Settings → Network → Firewall"
echo "  2. Click 'Options' or 'Firewall Options'"
echo "  3. Add your Python application or Terminal"
echo "  4. Set to 'Allow incoming connections'"
echo ""
echo "Option 2: Disable Firewall (Not Recommended)"
echo "  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off"
echo ""
echo "Option 3: Use pfctl (Advanced)"
echo "  See instructions in the guide"
echo ""
echo "=========================================="
echo "Testing Port Accessibility"
echo "=========================================="
echo ""
echo "To test if ports are accessible from outside:"
echo "  1. Find your public IP: curl ifconfig.me"
echo "  2. From another machine, test:"
for port in "${PORTS[@]}"; do
    echo "     nc -zv YOUR_PUBLIC_IP $port"
done
echo ""
echo "Or use an online port checker:"
echo "  https://www.yougetsignal.com/tools/open-ports/"
echo ""

# Get public IP
echo "📡 Your public IP address:"
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "Unable to determine")
echo "   $PUBLIC_IP"
echo ""

# Check if behind NAT/router
echo "🔍 Network Information:"
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "Unable to determine")
echo "   Local IP: $LOCAL_IP"
echo ""

if [[ "$PUBLIC_IP" != "$LOCAL_IP" ]]; then
    echo "⚠️  You appear to be behind a router/NAT"
    echo "   You may also need to configure port forwarding on your router:"
    echo "   - Port 8091 → $LOCAL_IP:8091"
    echo "   - Port 8092 → $LOCAL_IP:8092"
    echo ""
fi

echo "=========================================="
echo "Cloud Provider Firewall (if applicable)"
echo "=========================================="
echo ""
echo "If you're using a cloud provider (AWS, GCP, Azure, DigitalOcean, etc.):"
echo "  You need to configure Security Groups/Firewall rules:"
echo "  - Allow TCP port 8091 (inbound)"
echo "  - Allow TCP port 8092 (inbound)"
echo "  - Source: 0.0.0.0/0 (or specific IPs)"
echo ""

