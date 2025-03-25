#!/bin/bash
#
# rsync all of raspberry pi's local weather data files in /var/tmp/wx to Energy Systems lab linux machine
#
# Marc Compere, comperem@erau.edu
# created : 08 Dec 2023
# modified: 15 Mar 2025

# Set up environment for screen session
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
HOME=/home/pi

# Energy Systems lab, M.131 linux machine IP on wireless EagleNet network
MY_MACHINE="10.33.128.120"
CURRENT_DATE=$(date +%Y_%m_%d)
CURRENT_FILE="${CURRENT_DATE}_weather_station_data.csv"

while true; do
    CURRENT_DATE=$(date +%Y_%m_%d)
    CURRENT_FILE="${CURRENT_DATE}_weather_station_data.csv"

    if [ ! -f "/var/tmp/wx/$CURRENT_FILE" ]; then
        echo "$(date): Source file /var/tmp/wx/$CURRENT_FILE does not exist!"
        sleep 60
        continue
    fi

    # Get file size before sync
    SOURCE_SIZE=$(stat -c%s "/var/tmp/wx/$CURRENT_FILE" 2>/dev/null || echo "0")

    # Modified rsync command to only sync today's file and append to existing data
    # Using passwordless SSH
    echo "$(date): Starting rsync for $CURRENT_FILE"
    if ! rsync -v --append \
        -e "ssh -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
        "/var/tmp/wx/$CURRENT_FILE" \
        "pi@$MY_MACHINE:/var/tmp/wx/" 2>&1 | while read -r line; do
        echo "$(date): $line"
    done; then
        echo "$(date): Rsync failed!"
    fi

    sleep 30
done
