#!/bin/bash

# Check and install required packages
if ! command -v iw &> /dev/null; then
    echo "$(date): Installing required packages..."
    sudo apt-get install -y wireless-tools
fi

# Find the full path to iw command
IW_PATH=$(which iw 2>/dev/null || echo "/sbin/iw")

if [ ! -x "$IW_PATH" ]; then
    echo "$(date): Error: iw command not found. Please install wireless-tools package."
    exit 1
fi

SSID="EagleNet"  # Ensure this matches the exact SSID
CHECK_HOST="8.8.8.8"  # Google DNS for connectivity test
RETRY_INTERVAL=5  # Seconds before retrying

# Function to detect active WiFi interface
detect_interface() {
    $IW_PATH dev | awk '$1=="Interface"{print $2}' | head -n 1
}

while true; do
    WIFI_INTERFACE=$(detect_interface)

    if [ -z "$WIFI_INTERFACE" ]; then
        echo "$(date): No active WiFi interface detected, rescanning..."
        WIFI_INTERFACE=$(detect_interface)
    fi

    # If still no interface, retry
    if [ -z "$WIFI_INTERFACE" ]; then
        sleep $RETRY_INTERVAL
        continue
    fi

    # Check connectivity by pinging Google
    if ! ping -c 1 -W 2 $CHECK_HOST &> /dev/null; then
        echo "$(date): WiFi down on $WIFI_INTERFACE! Attempting reconnect..."

        # Soft reconnect
        nmcli device disconnect "$WIFI_INTERFACE"
        sleep 2
        nmcli device wifi connect "$SSID" ifname "$WIFI_INTERFACE"

        # If soft reconnect fails, reset the WiFi adapter
        sleep 10
        if ! nmcli device show "$WIFI_INTERFACE" | grep -q "GENERAL.STATE:.*connected"; then
            echo "$(date): Soft reconnect failed, resetting WiFi adapter..."
            sudo ip link set "$WIFI_INTERFACE" down
            sleep 5
            sudo ip link set "$WIFI_INTERFACE" up
            sleep 5
            nmcli device wifi connect "$SSID" ifname "$WIFI_INTERFACE"
        fi
    fi

    sleep $RETRY_INTERVAL
done
