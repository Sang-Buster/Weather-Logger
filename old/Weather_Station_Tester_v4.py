#!/usr/bin/env python3
"""
Weather Station Data Logger for RM Young 81000V Anemometer

This script collects and logs weather data from an RM Young 81000V Anemometer.
It operates in two modes:
- Continuous 1 Hz logging for long-term data collection
- On-demand 32 Hz high-frequency logging triggered by UDP commands

Original Created By: Avinash Muthu Krishna, muthukra@erau.edu
Modified By: Erik Liebergall, lieberge@my.erau.edu
             Marc Compere, comperem@erau.edu
             Sang Xing, xings@erau.edu

Version history:
- Version 2: Added .split() function to split the string rather than indicing
- Version 3: Added long term logging to a .csv with file rotation, symbolic link, and no-hassle restart
- Version 4: Added two threads for high frequency 32 Hz intermittent logging and slower 1 Hz constant logging
- Version 6: Added moving average filter to downsample 32 Hz data to 1 Hz for constant logging

TESTING MODE:
This version uses fake generated data incoming via UDP at 32Hz to mimic RM Young weather station.

Operation:
- RMYoung_WS_DummyData.py    - Starts the incoming generated data
- daily_logfile_rotator.py   - Handles log file rotation
- SDL_Starter.py             - Run once to start high frequency logging
- SDL_Stopper.py             - Run once to stop high frequency logging and return to 1 Hz mode

Output files:
- Low Frequency (1 Hz) log: /var/tmp/wx/YYYY_MM_DD_weather_station_data.csv
- High Frequency (32 Hz) log: [current_directory]/YYYY_MM_DD_HH_MM_SS_Anemometer.csv
"""

import logging
import os
import queue
import re
import select
import socket
import threading
import time
from datetime import datetime
from threading import Thread

import numpy as np
import pandas as pd
import serial
from daily_logfile_rotator import longDurationLogger as ldl
from roundOnlyRoundableDictKeys import roundOnlyRoundableDictKeys

# Configure logging - WARNING level to reduce debug messages
logging.basicConfig(
    level=logging.WARNING,  # Changed from INFO to WARNING to reduce debug messages
    format="[%(levelname)s] [%(threadName)-10s] %(message)s",
)

# Configure daily_logfile_rotator's logging level separately to suppress its messages
logging.getLogger("daily_logfile_rotator").setLevel(logging.WARNING)

# Configure serial connection to the anemometer
try:
    ser = serial.Serial("/dev/ttyUSB0", 38400, timeout=1)
    logging.info("Successfully connected to serial port /dev/ttyUSB0")
except Exception as e:
    logging.warning(f"Failed to open serial port: {e}")
    logging.info("Using simulated data mode")
    ser = None

# Initialize time tracking
tStart = time.time()

# Configure long duration logger
strftimeStr = "%Y_%m_%d"  # Format for daily log rotation
logDir = "/var/tmp/wx"
fieldnames = [
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
doFlush = True  # Set to True to ensure immediate file updates
myLdl = ldl(logDir, fieldnames, strftimeStr, doFlush)

# Debug and counter settings
errCnt = 0
debug = 0  # Debug level (0/1/2) - Setting to 0 to minimize debug output
cnt = 0
skipNth = 30  # Print every N'th cnt values

# UDP Server setup for data logging control
host = "localhost"
port1 = 8150  # Port for data receiving
port2 = 8250  # Port for control commands
status_port = 8251  # Port for status queries

server_socket1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_socket1.bind((host, port1))
server_socket2.bind((host, port2))
server_socket2.setblocking(False)  # Non-blocking socket for control

# Global variables
SDLStart = 0  # Start/stop flag for Short Data Logger (high frequency logging)
mode_changed = False  # Flag to track mode changes

# Initialize dataframe for storing data
ldlData = pd.DataFrame(
    columns=[
        "TIME",
        "U",
        "V",
        "W",
        "d2",
        "d3",
        "Az",
        "Ele_deg",
        "Press_raw",
        "Temp",
        "RH",
        "Sonic",
    ]
)

# State tracking variables
flg = 0  # Data processing flag
Pcnt = 0  # Processing counter
Dcnt = 0  # Display counter
titleLine = 0  # Flag for writing CSV header

# Create a file lock for thread-safe file operations
file_lock = threading.Lock()

# Rate control variables
last_1hz_update = 0
high_freq_rate = 1 / 32  # 32 Hz = 0.03125 seconds between samples
standard_rate = 1.0  # Standard rate (1 Hz) in seconds


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


def check_udp_command():
    """
    Check for incoming UDP commands to change the logging mode.

    Returns:
        bool: True if mode changed, False otherwise
    """
    global SDLStart, mode_changed

    # Check for control commands with a timeout
    try:
        # Use select to check if there's data to read with a timeout
        readable, _, _ = select.select([server_socket2], [], [], 0.001)

        if server_socket2 in readable:
            data, addr = server_socket2.recvfrom(4096)
            command = data.decode().strip()

            # Check if it's a status request
            if command.upper() == "STATUS":
                try:
                    # Try to send status back to the requestor
                    mode_str = "32Hz" if SDLStart > 0 else "1Hz"
                    status_msg = f"CURRENT_MODE:{mode_str}"
                    response_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    response_socket.sendto(
                        status_msg.encode(), ("localhost", status_port)
                    )
                except Exception as e:
                    logging.warning(f"Error sending status response: {e}")
                    pass
                return False  # No mode change, just status request

            # Try to convert command to float for mode change
            try:
                new_status = float(command)
                if new_status != SDLStart:
                    old_mode = "1 Hz" if SDLStart == 0 else "32 Hz"
                    new_mode = "32 Hz" if new_status > 0 else "1 Hz"

                    # Clear screen for visibility
                    print("\033[2J\033[H")  # ANSI escape codes to clear screen
                    print("=" * 80)
                    print(f"MODE CHANGE DETECTED: {old_mode} -> {new_mode}")
                    print("=" * 80)

                    if new_status > 0:
                        print("\n*** SWITCHING TO HIGH FREQUENCY (32 Hz) MODE ***\n")
                    else:
                        print("\n*** SWITCHING BACK TO STANDARD (1 Hz) MODE ***\n")

                    SDLStart = new_status
                    mode_changed = True
                    return True
            except ValueError:
                # Not a valid float command
                pass

    except Exception as e:
        # No data or error reading
        logging.error(f"Error checking UDP command: {e}")
        pass

    return False


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


def format_data_display(data_dict):
    """
    Format weather data for display in the console.

    Args:
        data_dict: Dictionary containing weather data

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
    mode = "32 Hz" if SDLStart > 0 else "1 Hz"
    display += f"  Logging Mode: {mode}\n"
    display += f"  Error Count: {data_dict['Error']}\n"
    display += "=" * 80 + "\n"

    return display


class ThreadSDL:
    """
    Thread handler for Short Data Logger (SDL) - High frequency (32 Hz) logging.

    Listens for UDP control commands to start/stop high frequency logging and
    processes the data queue for writing to the high frequency log file.
    """

    def Display(self, exit_event, data_queue):
        """
        Main thread function that processes incoming control commands and data.

        Args:
            exit_event: Threading event to signal thread termination
            data_queue: Queue containing data to be logged
        """
        global SDLStart, mode_changed
        last_write_time = 0

        while not exit_event.is_set():
            # Check if mode has been changed by the main thread
            if mode_changed:
                if SDLStart > 0:
                    print("SDL Thread: High frequency logging activated")
                else:
                    print("SDL Thread: High frequency logging deactivated")
                mode_changed = False  # Reset the flag

            # Process data if available in queue and in high-frequency mode
            if not data_queue.empty() and SDLStart > 0:
                # Rate limiting for 32Hz mode
                current_time = time.time()
                if current_time - last_write_time < high_freq_rate:
                    time.sleep(0.001)  # Brief pause to maintain rate
                    continue

                new_data = data_queue.get()
                last_write_time = current_time

                # Format data string for logging with microsecond precision
                data_str = "{0}, {1:.4f}, {2:.4f}, {3:.4f}, {4:.4f}, {5:.4f}, {6:.4f}, {7:.4f}, {8:.4f}, {9:.4f}, {10:.4f}, {11:.4f}, {12}\n".format(
                    format_timestamp(
                        new_data[0], include_microseconds=True
                    ),  # Include microseconds for 32Hz
                    new_data[1],
                    new_data[2],
                    new_data[3],
                    new_data[4],
                    new_data[5],
                    new_data[6],
                    new_data[7],
                    new_data[8],
                    new_data[9],
                    new_data[10],
                    new_data[11],
                    new_data[12],
                )

                # Write data to the same files as the low-frequency logger
                with file_lock:
                    try:
                        # Write to the daily log file
                        myLdl.fd_log.write(data_str)
                        myLdl.fd_log.flush()  # Force immediate write to disk
                    except Exception as e:
                        logging.warning(f"Error writing high-frequency data: {e}")
            else:
                # When no data or not in high-frequency mode
                time.sleep(0.001)


class ThreadLDL:
    """
    Thread handler for Long Data Logger (LDL) - Low frequency (1 Hz) continuous logging.

    Processes the data queue, downsamples from 32 Hz to 1 Hz using averaging,
    and writes to the long-term log file.
    """

    def Display(self, exit_event, data_queue):
        """
        Main thread function that processes and downsamples data.

        Args:
            exit_event: Threading event to signal thread termination
            data_queue: Queue containing data to be processed and logged
        """
        global flg, Pcnt, Dcnt, ldlData, last_1hz_update, mode_changed
        last_data = None
        buffer_limit = 32  # Maximum buffer size for 32Hz to 1Hz conversion

        # Print current mode status
        print("\nRunning in STANDARD (1 Hz) MODE\n")

        while not exit_event.is_set():
            # Check if mode has been changed
            if mode_changed:
                if SDLStart > 0:
                    print("LDL Thread: Switching to support 32Hz mode")
                else:
                    print("LDL Thread: Resuming standard 1Hz mode")

                # Continue without resetting flag - main thread will reset it

            current_time = time.time()
            enough_data_for_1hz = ldlData.shape[0] >= buffer_limit
            time_for_1hz_update = (current_time - last_1hz_update) >= standard_rate

            # Process incoming data (empty the queue)
            while not data_queue.empty():
                # Get data from queue
                data_array = data_queue.get()
                last_data = data_array  # Save for display

                # Add data to dataframe
                ldlData = concat_data(ldlData, data_array)

                # Maintain fixed size buffer by removing oldest data when exceeding limit
                if ldlData.shape[0] > buffer_limit:
                    ldlData = ldlData.iloc[-buffer_limit:]

            # Check if it's time to generate a 1Hz update
            if time_for_1hz_update and last_data is not None:
                try:
                    # Reset timestamp for next 1Hz update (do this first to maintain timing)
                    last_1hz_update = current_time

                    # Create a timestamp that's exactly on the second (truncate microseconds)
                    exact_second_timestamp = datetime.now().replace(microsecond=0)

                    # If we have enough data, use averaging, otherwise use latest value
                    if enough_data_for_1hz:
                        # Convert to datetime and resample to 1Hz
                        ldlData["TIME"] = pd.to_datetime(ldlData["TIME"])
                        ldlData.set_index("TIME", inplace=True)
                        downsampled_data = ldlData.resample("1s").mean()

                        # Reset dataframe for next cycle
                        downsampled_data.reset_index(inplace=True)
                        ldlData.reset_index(inplace=True)

                        if not downsampled_data.empty:
                            # Create dictionary for log file writing
                            my_data = {
                                "tNow": exact_second_timestamp,  # Use timestamp without microseconds for 1Hz logs
                                "u_m_s": downsampled_data["U"][0],
                                "v_m_s": downsampled_data["V"][0],
                                "w_m_s": downsampled_data["W"][0],
                                "2dSpeed_m_s": downsampled_data["d2"][0],
                                "3DSpeed_m_s": downsampled_data["d3"][0],
                                "Azimuth_deg": downsampled_data["Az"][0],
                                "Elev_deg": downsampled_data["Ele_deg"][0],
                                "Press_Pa": downsampled_data["Press_raw"][0],
                                "Temp_C": downsampled_data["Temp"][0],
                                "Hum_RH": downsampled_data["RH"][0],
                                "SonicTemp_C": downsampled_data["Sonic"][0],
                                "Error": last_data[12],  # Use latest error count
                            }
                    else:
                        # Not enough data for averaging, use the last value directly
                        my_data = {
                            "tNow": exact_second_timestamp,  # Use timestamp without microseconds for 1Hz logs
                            "u_m_s": last_data[1],
                            "v_m_s": last_data[2],
                            "w_m_s": last_data[3],
                            "2dSpeed_m_s": last_data[4],
                            "3DSpeed_m_s": last_data[5],
                            "Azimuth_deg": last_data[6],
                            "Elev_deg": last_data[7],
                            "Press_Pa": last_data[8],
                            "Temp_C": last_data[9],
                            "Hum_RH": last_data[10],
                            "SonicTemp_C": last_data[11],
                            "Error": last_data[12],
                        }

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
                    my_data_rounded = roundOnlyRoundableDictKeys(my_data, keys_to_round)

                    # Display formatted data at 1Hz rate (when not in 32Hz mode)
                    if SDLStart == 0:
                        print(format_data_display(my_data_rounded))

                    # Write data to long-term log file
                    myLdl.writeLogfile(my_data_rounded)

                    Dcnt += 1
                except Exception as e:
                    # Using warning level to prevent flooding console
                    logging.warning(f"Error processing data for 1Hz output: {e}")

                # Reset counter after processing
                Pcnt = 0

            # Small sleep to prevent CPU hogging
            time.sleep(0.01)


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


def read_serial_data():
    """
    Read data from the serial port or generate simulated data.

    Returns:
        tuple: (success, values) where success is a boolean and values is a list of data
    """
    global errCnt

    try:
        if ser is not None:
            # Read from actual serial port
            data = ser.read_until(b"\r")

            try:
                # Clean the data before decoding
                data_clean = data.replace(b"\x00", b"")  # Remove null bytes
                data_decoded = data_clean.decode().strip()
                values = data_decoded.split()

                # Validate that we have enough data points
                if len(values) < 12:
                    # Too few values, use simulated data
                    errCnt += 1
                    return False, generate_simulated_data()

                # Clean each value
                cleaned_values = [clean_sensor_value(val) for val in values]
                return True, cleaned_values

            except UnicodeDecodeError:
                errCnt += 1
                return False, generate_simulated_data()
            except Exception:
                errCnt += 1
                return False, generate_simulated_data()
        else:
            # Generate simulated data when no serial connection
            return True, generate_simulated_data()

    except Exception:
        errCnt += 1
        return False, generate_simulated_data()


def main():
    """
    Main function to initialize threads and process sensor data.
    """
    global errCnt, last_1hz_update, SDLStart, mode_changed

    # Set initial 1Hz update time
    last_1hz_update = time.time()

    # Create exit event and data queues
    exit_event = threading.Event()
    queue_sdl = queue.Queue(
        maxsize=100
    )  # Limited queue size for high frequency logging
    queue_ldl = queue.Queue(maxsize=100)  # Limited queue size for low frequency logging

    # Initialize thread objects
    thread_sdl = ThreadSDL()
    thread_ldl = ThreadLDL()

    # Create and start threads
    t1 = Thread(
        target=thread_sdl.Display, args=(exit_event, queue_sdl), name="HighFreqLogger"
    )
    t2 = Thread(
        target=thread_ldl.Display, args=(exit_event, queue_ldl), name="LowFreqLogger"
    )

    t1.start()
    t2.start()

    print("Starting data collector loop - Press Ctrl+C to stop the program")

    try:
        # Track timing for rate control
        last_data_time = time.time()

        # Set initial collection rate (in seconds per reading)
        data_interval = standard_rate / 10  # Default to 10Hz collection for 1Hz output

        # Periodically check mode indicator (at most every 5 seconds)
        mode_check_time = time.time()
        mode_check_interval = 5.0  # seconds

        while True:
            # Check for UDP commands periodically
            current_time = time.time()
            if check_udp_command():
                # Mode changed - adjust data collection rate
                if SDLStart > 0:
                    data_interval = high_freq_rate
                    print("MAIN: Switching to high frequency (32 Hz) data collection")
                else:
                    data_interval = standard_rate / 10
                    print("MAIN: Switching to standard (1 Hz) data collection")

            # Periodically display current mode (helpful for troubleshooting)
            if current_time - mode_check_time > mode_check_interval:
                mode_str = (
                    "HIGH FREQUENCY (32 Hz)" if SDLStart > 0 else "STANDARD (1 Hz)"
                )
                print(f"Current mode: {mode_str}")
                mode_check_time = current_time

            # Wait until it's time for the next sample
            time_since_last = current_time - last_data_time
            if time_since_last < data_interval:
                sleep_time = data_interval - time_since_last
                time.sleep(
                    max(0.001, sleep_time)
                )  # Minimum sleep to prevent CPU thrashing
                continue

            # Read data from serial port or generate simulated data
            success, values = read_serial_data()
            last_data_time = time.time()  # Update last read time

            # Prepare precise timestamps based on mode
            if SDLStart > 0:
                # For high frequency mode - include microseconds
                t_now = datetime.now()
            else:
                # For standard mode - round to the nearest second
                t_now = datetime.now().replace(microsecond=0)

            # Parse sensor values
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

            except Exception:
                # Use simulated values on error
                u = v = w = d2 = d3 = az = ele = 0.0
                corrected_press = corrected_temp = corrected_rh = sonic = 0.0
                err_count = errCnt

            # Create array of data values
            queue_data = np.array(
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
                    time.time(),
                    time.time(),
                    0,
                ]
            )

            # Add data to both queues, but don't block if queue is full
            try:
                queue_sdl.put(queue_data, block=False)
            except queue.Full:
                # Skip this data point for SDL if queue is full
                pass

            try:
                queue_ldl.put(queue_data, block=False)
            except queue.Full:
                # Skip this data point for LDL if queue is full
                pass

    except KeyboardInterrupt:
        print("\nCaught KeyboardInterrupt, closing logfiles and exiting!")
        exit_event.set()  # Signal threads to exit
        myLdl.e.set()  # Tell long duration logger threads to exit

        # Make sure all files are properly closed
        try:
            myLdl.fd_log.flush()
            myLdl.fd_log.close()
        except Exception as e:
            logging.warning(f"Error closing log file: {e}")
            pass

        if ser is not None:
            ser.close()

        print(f"\nEnd time: {time.ctime()}")
        elapsed_time = time.time() - tStart  # Calculate elapsed time
        print(f"Exiting after running for {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    # Create a clean start with a welcome message
    os.system("clear")
    print("=" * 80)
    print("                     WEATHER STATION DATA LOGGER")
    print("=" * 80)
    print("\nStarting data collection in standard 1 Hz mode...\n")
    print("Controls:")
    print("- Press Ctrl+C to exit")
    print("- Run SDL_Starter.py to begin high-frequency (32 Hz) logging")
    print("- Run SDL_Stopper.py to stop high-frequency logging and return to 1 Hz mode")
    print("\nLog files:")
    print(f"- 1 Hz data: {logDir}/YYYY_MM_DD_weather_station_data.csv")
    print(
        "- 32 Hz data: [current directory]/YYYY_MM_DD_HH_MM_SS_Anemometer.csv (when enabled)"
    )
    print("=" * 80)
    time.sleep(2)

    main()
