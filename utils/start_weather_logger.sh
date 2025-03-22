#!/bin/bash

# Change to the weather dashboard directory
cd /home/pi/Desktop/weather_logger || exit

# Activate virtual environment
source .venv/bin/activate

# Start the application inside a screen session
screen -dmS weather_logger bash -c "uv run src/weather_station.py"
echo "Weather Station Tester started in screen session: weather_logger"
