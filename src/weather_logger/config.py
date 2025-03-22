#!/usr/bin/env python3
"""
Configuration settings for the Weather Logger

This module contains all the configuration settings for the Weather Station Data Logger.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Configure logging - WARNING level to reduce debug messages by default
# This can be overridden by setting DEBUG > 0
logging.basicConfig(
    level=logging.WARNING,
    format="[%(levelname)s] [%(threadName)-10s] [%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)

# Configure daily_logfile_rotator's logging level separately to suppress its messages
logging.getLogger("daily_logfile_rotator").setLevel(logging.WARNING)

# Serial port configuration
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
SERIAL_BAUDRATE = int(os.getenv("SERIAL_BAUDRATE", "38400"))
SERIAL_TIMEOUT = int(os.getenv("SERIAL_TIMEOUT", "1"))

# Logger configuration
LOG_DIR = os.getenv("LOG_DIR", "/var/tmp/wx")
STRFTIME_STR = "%Y_%m_%d"  # Format for daily log rotation
DO_FLUSH = os.getenv("DO_FLUSH", "True").lower() in ("true", "1", "t")

# UDP Server configuration
HOST = os.getenv("HOST", "localhost")
PORT_DATA = int(os.getenv("PORT_DATA", "8150"))  # Port for data receiving
PORT_CONTROL = int(os.getenv("PORT_CONTROL", "8250"))  # Port for control commands
PORT_STATUS = int(os.getenv("PORT_STATUS", "8251"))  # Port for status queries

# Visualization server settings
UDP_IP = os.getenv("UDP_IP", "127.0.0.1")  # Default to localhost
UDP_PORT = int(os.getenv("UDP_PORT", "5555"))  # UDP port for the visualization server

# Data collection rates
HIGH_FREQ_RATE = 1 / float(os.getenv("HIGH_FREQ_RATE", "32"))  # Default 32 Hz
STANDARD_RATE = float(os.getenv("STANDARD_RATE", "1.0"))  # Default 1 Hz

# Field names for logging
FIELDNAMES = [
    "tNow",
    "u_m_s",
    "v_m_s",
    "w_m_s",
    "2dSpeed_m_s",
    "3DSpeed_m_s",
    "Azimuth_deg",
    "Elev_deg",
    "Press_Pa",
    "Temp_C",
    "Hum_RH",
    "SonicTemp_C",
    "Error",
]

# Debug settings
# 0 = minimal output (WARNING level)
# 1 = more detailed output (INFO level)
# 2 = debug output (DEBUG level)
DEBUG = int(os.getenv("DEBUG", "1"))  # Default to INFO level logging
