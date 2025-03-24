#!/bin/bash

# Activate virtual environment
source /home/pi/Desktop/weather_logger/.venv/bin/activate

# Add local bin directory to PATH
export PATH=$PATH:/home/pi/.local/bin

# Find uv executable
UV_CMD=$(which uv)
if [ -z "$UV_CMD" ]; then
    echo "Error: uv command not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV_CMD=$(which uv)
    if [ -z "$UV_CMD" ]; then
        echo "Failed to install uv. Falling back to python directly."
        python /home/pi/Desktop/weather_logger/src/weather_station.py
    else
        $UV_CMD run /home/pi/Desktop/weather_logger/src/weather_station.py
    fi
else
    $UV_CMD run /home/pi/Desktop/weather_logger/src/weather_station.py
fi

echo "Weather Station Tester started in screen session: weather_logger"

exec bash
