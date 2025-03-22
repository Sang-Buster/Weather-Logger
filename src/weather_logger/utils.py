#!/usr/bin/env python3
"""
Utility functions for Weather Logger

This module contains utility functions used across the Weather Logger application.
"""

import re

import numpy as np


def format_timestamp(timestamp, include_microseconds=False):
    """
    Format a datetime timestamp with or without microseconds.

    Args:
        timestamp: datetime object to format
        include_microseconds: whether to include microseconds in the output

    Returns:
        str: Formatted timestamp string
    """
    if include_microseconds:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
    else:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def is_valid_float_string(s):
    """
    Check if a string can be properly converted to a float.

    Args:
        s: String to check

    Returns:
        bool: True if string can be converted to float
    """
    # Filter out common corruption patterns
    if not isinstance(s, str):
        return False

    # Remove any non-printable characters
    s = "".join(c for c in s if c.isprintable())

    # Check for empty string after cleaning
    if not s:
        return False

    # Basic pattern for valid float
    pattern = r"^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$"
    return bool(re.match(pattern, s))


def clean_sensor_value(value_str):
    """
    Clean a sensor value string to remove any non-printable characters.

    Args:
        value_str: String to clean

    Returns:
        str: Cleaned string or default value if cleaning fails
    """
    if not isinstance(value_str, str):
        return "0.0"

    # Remove any non-printable characters
    cleaned = "".join(c for c in value_str if c.isprintable())

    # Check if the result is still a valid float-convertible string
    if is_valid_float_string(cleaned):
        return cleaned
    else:
        return "0.0"


def generate_simulated_data():
    """
    Generate simulated weather data for testing when actual serial data is unavailable.

    Returns:
        list: Simulated data values as strings
    """
    return [
        str(np.random.uniform(-10, 10)),  # U (m/s)
        str(np.random.uniform(-10, 10)),  # V (m/s)
        str(np.random.uniform(-10, 10)),  # W (m/s)
        str(np.random.uniform(0, 20)),  # 2DSpeed (m/s)
        str(np.random.uniform(0, 30)),  # 3D Speed (m/s)
        str(np.random.uniform(0, 360)),  # Azimuth (deg)
        str(np.random.uniform(-90, 90)),  # Elevation (deg)
        str(np.random.uniform(3000, 4000)),  # Pressure raw (Pa)
        str(np.random.uniform(2700, 3000)),  # Temperature raw (C)
        str(np.random.uniform(2000, 3000)),  # RH raw (%)
        str(np.random.uniform(15, 35)),  # Sonic Temperature (C)
        "0",  # Error count
    ]


def round_only_roundable_dict_keys(my_data, keys_to_round):
    """
    Round only specified keys in a dictionary that can be rounded.

    Args:
        my_data (dict): Dictionary with values to potentially round
        keys_to_round (list): List of dictionary keys to round

    Returns:
        dict: New dictionary with specified keys rounded
    """
    my_data_rounded = {}
    for key in my_data:
        if key in keys_to_round:
            my_data_rounded[key] = round(my_data[key], 8)
        else:
            my_data_rounded[key] = my_data[key]
    return my_data_rounded
