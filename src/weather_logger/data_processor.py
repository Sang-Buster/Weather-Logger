#!/usr/bin/env python3
"""
Data processing for Weather Logger

This module contains functions for processing weather data from the anemometer.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from .utils import round_only_roundable_dict_keys


def concat_data(df1, data_array):
    """
    Efficiently concatenate new data row to existing dataframe.

    Args:
        df1: Existing pandas DataFrame
        data_array: Array of new data values to add

    Returns:
        Updated DataFrame with new row added
    """
    # Create a new DataFrame with the data
    df2 = pd.DataFrame(
        {
            "TIME": [data_array[0]],
            "U": [data_array[1]],
            "V": [data_array[2]],
            "W": [data_array[3]],
            "d2": [data_array[4]],
            "d3": [data_array[5]],
            "Az": [data_array[6]],
            "Ele_deg": [data_array[7]],
            "Press_raw": [data_array[8]],
            "Temp": [data_array[9]],
            "RH": [data_array[10]],
            "Sonic": [data_array[11]],
        }
    )

    # Concatenate the DataFrames
    if df1.empty:
        result = df2
    else:
        result = pd.concat([df1, df2], ignore_index=True)
    return result


def process_raw_data(values, error_count):
    """
    Process raw sensor values into calibrated measurements.

    Args:
        values: List of string values from the anemometer
        error_count: Current error count

    Returns:
        tuple: (processed_values, data_dict) containing processed numerical values
               and a dictionary with labeled data
    """
    try:
        n = 0
        u = float(values[n])  # U (m/s)
        v = float(values[n + 1])  # V (m/s)
        w = float(values[n + 2])  # W (m/s)
        d2 = float(values[n + 3])  # 2DSpeed (m/s)
        d3 = float(values[n + 4])  # 3D Speed (m/s)
        az = float(values[n + 5])  # Azimuth (deg)
        ele = float(values[n + 6])  # Elevation (m)
        press_raw = float(values[n + 7])  # Pressure (Pa)
        temp = float(values[n + 8])  # Temperature (C)
        rh = float(values[n + 9])  # Relative Humidity (%)
        sonic = float(values[n + 10])  # Sonic Temperature (C)
        err_count = float(values[n + 11])  # Error Count

        # Correct pressure, temperature, and humidity values
        corrected_press = (0.02 * press_raw + 950) * 100  # Avi's equation
        corrected_temp = (100.0 * (1.0 / 4000) * temp) - 50.0  # Temp conversion
        corrected_rh = 100 * (1.0 / 4000) * rh  # RH conversion

    except IndexError as e:
        # Specific handling for index errors (not enough values)
        logging.error(f"Index error processing raw data: {e}, values: {values}")
        u = v = w = d2 = d3 = az = ele = 0.0
        corrected_press = corrected_temp = corrected_rh = sonic = 0.0
        err_count = error_count + 1  # Increment error count
    except ValueError as e:
        # Specific handling for value errors (can't convert to float)
        logging.error(f"Value error processing raw data: {e}, values: {values}")
        u = v = w = d2 = d3 = az = ele = 0.0
        corrected_press = corrected_temp = corrected_rh = sonic = 0.0
        err_count = error_count + 1  # Increment error count
    except Exception as e:
        # Generic error handling
        logging.error(f"Unexpected error processing raw data: {e}, values: {values}")
        u = v = w = d2 = d3 = az = ele = 0.0
        corrected_press = corrected_temp = corrected_rh = sonic = 0.0
        err_count = error_count + 1  # Increment error count

    # Get current timestamp
    t_now = datetime.now()

    # Create data dictionary
    data_dict = {
        "tNow": t_now,
        "u_m_s": u,
        "v_m_s": v,
        "w_m_s": w,
        "2dSpeed_m_s": d2,
        "3DSpeed_m_s": d3,
        "Azimuth_deg": az,
        "Elev_deg": ele,
        "Press_Pa": corrected_press,
        "Temp_C": corrected_temp,
        "Hum_RH": corrected_rh,
        "SonicTemp_C": sonic,
        "Error": err_count,
    }

    # Create array of processed values
    processed_values = np.array(
        [
            t_now,
            u,
            v,
            w,
            d2,
            d3,
            az,
            ele,
            corrected_press,
            corrected_temp,
            corrected_rh,
            sonic,
            err_count,
        ]
    )

    return processed_values, data_dict


def prepare_data_for_logging(data_dict):
    """
    Prepare data for logging by rounding numeric values.

    Args:
        data_dict: Dictionary containing data values

    Returns:
        dict: Dictionary with rounded numeric values
    """
    # Round numeric values for better readability
    keys_to_round = [
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
    return round_only_roundable_dict_keys(data_dict, keys_to_round)


def downsample_data(df_data, buffer_limit=32):
    """
    Downsample high frequency data to 1Hz using averaging.

    Args:
        df_data: DataFrame containing high frequency data
        buffer_limit: Maximum buffer size for downsampling

    Returns:
        DataFrame: Downsampled data at 1Hz
    """
    # Ensure dataframe isn't larger than buffer limit
    if df_data.shape[0] > buffer_limit:
        df_data = df_data.iloc[-buffer_limit:]

    # Convert to datetime and resample to 1Hz if we have enough data
    if df_data.shape[0] >= buffer_limit:
        df_data["TIME"] = pd.to_datetime(df_data["TIME"])
        df_data.set_index("TIME", inplace=True)
        downsampled_data = df_data.resample("1s").mean()

        # Reset index for further processing
        downsampled_data.reset_index(inplace=True)
        df_data.reset_index(inplace=True)

        return downsampled_data

    return None
