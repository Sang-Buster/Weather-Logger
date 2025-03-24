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

# Use a log in the home directory where pi user has write access
LOG_FILE="$HOME/wifi_reconnect.log"
SSID="EagleNet"  # Ensure this matches the exact SSID
CHECK_HOST="8.8.8.8"  # Google DNS for connectivity test
RETRY_INTERVAL=5  # Seconds before retrying
LAST_STATUS="unknown"

# Create log file if it doesn't exist (or just ignore errors)
touch "$LOG_FILE" 2>/dev/null || true

# Print and log a message
log_message() {
    local msg="$(date): $1"
    echo "$msg"
    # Redirect errors to /dev/null to prevent error messages
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

# Display network status 
show_network_info() {
    local interface=$1
    log_message "Network info for $interface:"
    
    # Get IP addresses - format them properly
    local ip_count=0
    while read -r ip_line; do
        if [ -n "$ip_line" ]; then
            ip_count=$((ip_count+1))
            log_message "IP Address $ip_count: $ip_line"
        fi
    done < <(ip addr show $interface | grep -E "inet " | awk '{print $2}')
    
    if [ $ip_count -eq 0 ]; then
        log_message "No IP addresses found"
    fi
    
    # Get WiFi signal strength
    local signal=$(iwconfig $interface 2>/dev/null | grep -i "quality" | awk '{print $2}' | sed 's/Quality=//')
    if [ -n "$signal" ]; then
        log_message "Signal: $signal"
    fi
    
    # Check connectivity
    if ping -c 1 -W 2 $CHECK_HOST &> /dev/null; then
        log_message "Internet connectivity: OK"
    else
        log_message "Internet connectivity: FAILED"
    fi
}

# Function to detect active WiFi interface
detect_interface() {
    $IW_PATH dev | awk '$1=="Interface"{print $2}' | head -n 1
}

# Initial startup message
log_message "WiFi auto-reconnect service started"

while true; do
    WIFI_INTERFACE=$(detect_interface)

    if [ -z "$WIFI_INTERFACE" ]; then
        log_message "No active WiFi interface detected, rescanning..."
        WIFI_INTERFACE=$(detect_interface)
    fi

    # If still no interface, retry
    if [ -z "$WIFI_INTERFACE" ]; then
        sleep $RETRY_INTERVAL
        continue
    fi

    # Check connectivity by pinging Google
    if ! ping -c 1 -W 2 $CHECK_HOST &> /dev/null; then
        # Only log if this is a new disconnect event
        if [ "$LAST_STATUS" != "disconnected" ]; then
            log_message "WiFi down on $WIFI_INTERFACE! Attempting reconnect..."
            LAST_STATUS="disconnected"
        fi

        # Soft reconnect
        nmcli device disconnect "$WIFI_INTERFACE" &>/dev/null
        sleep 2
        nmcli device wifi connect "$SSID" ifname "$WIFI_INTERFACE" &>/dev/null
        reconnect_result=$?

        # Check if connection successful
        sleep 5
        if ping -c 1 -W 2 $CHECK_HOST &> /dev/null; then
            log_message "WiFi reconnected successfully!"
            show_network_info "$WIFI_INTERFACE"
            LAST_STATUS="connected"
        # If soft reconnect fails, reset the WiFi adapter
        else
            log_message "Soft reconnect failed, resetting WiFi adapter..."
            sudo ip link set "$WIFI_INTERFACE" down
            sleep 5
            sudo ip link set "$WIFI_INTERFACE" up
            sleep 5
            nmcli device wifi connect "$SSID" ifname "$WIFI_INTERFACE" &>/dev/null
            
            # Check if hard reset worked
            sleep 5
            if ping -c 1 -W 2 $CHECK_HOST &> /dev/null; then
                log_message "WiFi reconnected after adapter reset!"
                show_network_info "$WIFI_INTERFACE"
                LAST_STATUS="connected"
            else
                log_message "WiFi reconnection FAILED even after adapter reset"
                LAST_STATUS="failed"
            fi
        fi
    elif [ "$LAST_STATUS" != "connected" ]; then
        # Only show this on status changes to avoid cluttering the log
        log_message "WiFi connection is stable"
        show_network_info "$WIFI_INTERFACE"
        LAST_STATUS="connected"
    fi

    sleep $RETRY_INTERVAL
done
