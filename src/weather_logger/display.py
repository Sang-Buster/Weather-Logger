#!/usr/bin/env python3
"""
Display formatting for Weather Logger

This module handles formatting and display of weather data in the console.
"""


def format_data_display(data_dict, current_mode="1 Hz"):
    """
    Format weather data for display in the console.

    Args:
        data_dict: Dictionary containing weather data
        current_mode: Current logging mode ("1 Hz" or "32 Hz")

    Returns:
        str: Formatted string for display
    """
    # Create a clean, aligned display of the current weather data
    display = "\033[2J\033[H"  # Clear screen and move cursor to top
    display += "=" * 80 + "\n"
    display += "WEATHER STATION DATA - {}\n".format(
        data_dict["tNow"].strftime("%Y-%m-%d %H:%M:%S")
    )
    display += "=" * 80 + "\n\n"

    # Wind components
    display += "WIND COMPONENTS:\n"
    display += f"  U: {data_dict['u_m_s']:7.2f} m/s    "
    display += f"V: {data_dict['v_m_s']:7.2f} m/s    "
    display += f"W: {data_dict['w_m_s']:7.2f} m/s\n"

    # Wind speeds
    display += f"  2D Speed: {data_dict['2dSpeed_m_s']:7.2f} m/s    "
    display += f"3D Speed: {data_dict['3DSpeed_m_s']:7.2f} m/s\n"

    # Direction
    display += f"  Azimuth: {data_dict['Azimuth_deg']:7.2f}°    "
    display += f"Elevation: {data_dict['Elev_deg']:7.2f}°\n\n"

    # Environmental conditions
    display += "ENVIRONMENTAL CONDITIONS:\n"
    display += f"  Pressure: {data_dict['Press_Pa']:10.2f} Pa    "
    display += f"Temperature: {data_dict['Temp_C']:6.2f} °C\n"
    display += f"  Humidity: {data_dict['Hum_RH']:7.2f} %    "
    display += f"Sonic Temp: {data_dict['SonicTemp_C']:6.2f} °C\n\n"

    # Logging status
    display += "LOGGING STATUS:\n"
    display += f"  Logging Mode: {current_mode}\n"
    display += f"  Error Count: {data_dict['Error']}\n"
    display += "=" * 80 + "\n"

    return display


def print_welcome_message(log_dir):
    """
    Display a welcome message when starting the weather station.

    Args:
        log_dir: Directory where log files are stored
    """
    print("=" * 80)
    print("                     WEATHER STATION DATA LOGGER")
    print("=" * 80)
    print("\nStarting data collection in standard 1 Hz mode...\n")
    print("Controls:")
    print("- Press Ctrl+C to exit")
    print("- Run sdl_high.py to begin high-frequency (32 Hz) logging")
    print("- Run sdl_low.py to stop high-frequency logging and return to 1 Hz mode")
    print("\nLog files:")
    print(f"- 1 Hz data: {log_dir}/YYYY_MM_DD_weather_station_data.csv")
    print("- 32 Hz data: Included in the same log file when 32 Hz logging is enabled")
    print("=" * 80)
