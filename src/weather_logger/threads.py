#!/usr/bin/env python3
"""
Thread classes for Weather Logger

This module contains thread classes for handling different aspects of the
weather logging process.
"""

import logging
import time
from datetime import datetime

import pandas as pd

from .data_processor import concat_data, prepare_data_for_logging
from .display import format_data_display


class HighFrequencyLogger:
    """
    Thread handler for high frequency (32 Hz) logging.

    Processes the data queue for writing to the high frequency log file.
    """

    def __init__(self, high_freq_rate):
        """
        Initialize the high frequency logger.

        Args:
            high_freq_rate: Rate for high frequency logging (seconds)
        """
        self.high_freq_rate = high_freq_rate
        self.mode_changed = False

    def run(self, exit_event, data_queue, file_lock, data_logger, sdl_mode):
        """
        Main thread function that processes data for high frequency logging.

        Args:
            exit_event: Threading event to signal thread termination
            data_queue: Queue containing data to be logged
            file_lock: Lock for thread-safe file operations
            data_logger: Logger instance for writing data
            sdl_mode: Shared object containing current mode (SDL_START value)
        """
        logging.info("High frequency logging thread started")
        last_write_time = 0
        last_mode = 0

        while not exit_event.is_set():
            # Check if mode has changed
            current_mode = sdl_mode.value
            if current_mode != last_mode:
                last_mode = current_mode
                if current_mode > 0:
                    logging.info("High frequency logger activated")
                    print(
                        "High frequency logger is now active and processing data at 32 Hz"
                    )
                    # Force immediate display refresh
                    with file_lock:
                        # Clear any data already in queue when activating to start fresh
                        self._clear_queue(data_queue)
                else:
                    logging.info("High frequency logger deactivated")
                    # Clear the queue when switching back to standard mode to prevent overflow
                    self._clear_queue(data_queue)
                self.mode_changed = True

            # Check if high-frequency mode is active
            if not data_queue.empty() and sdl_mode.value > 0:
                # Rate limiting for 32Hz mode
                current_time = time.time()
                if current_time - last_write_time < self.high_freq_rate:
                    time.sleep(0.001)  # Brief pause to maintain rate
                    continue

                # Get data from queue
                new_data = data_queue.get()
                last_write_time = current_time

                # Log processing status periodically if in debug mode
                if self.mode_changed:
                    logging.info(
                        f"Processing high-frequency data point at time {new_data[0]}"
                    )
                    self.mode_changed = False

                # Format data string for logging with microsecond precision
                timestamp = new_data[0]

                # Create a dictionary for data logging
                data_dict = {
                    "tNow": timestamp,
                    "u_m_s": new_data[1],
                    "v_m_s": new_data[2],
                    "w_m_s": new_data[3],
                    "2dSpeed_m_s": new_data[4],
                    "3DSpeed_m_s": new_data[5],
                    "Azimuth_deg": new_data[6],
                    "Elev_deg": new_data[7],
                    "Press_Pa": new_data[8],
                    "Temp_C": new_data[9],
                    "Hum_RH": new_data[10],
                    "SonicTemp_C": new_data[11],
                    "Error": new_data[12],
                }

                # Prepare data for logging (round values)
                rounded_data = prepare_data_for_logging(data_dict)

                # Write data to log file (thread-safe)
                with file_lock:
                    try:
                        data_logger.write_logfile(rounded_data)
                    except Exception as e:
                        logging.warning(f"Error writing high-frequency data: {e}")
            else:
                # When no data or not in high-frequency mode
                time.sleep(0.001)

    def _clear_queue(self, queue):
        """Clear all items from the queue to prevent overflow when mode changes"""
        try:
            while not queue.empty():
                queue.get_nowait()
            logging.info("High frequency queue cleared after mode change")
        except Exception as e:
            logging.warning(f"Error clearing high frequency queue: {e}")


class StandardLogger:
    """
    Thread handler for standard (1 Hz) continuous logging.

    Processes the data queue, downsamples from 32 Hz to 1 Hz using averaging,
    and writes to the log file.
    """

    def __init__(self, standard_rate):
        """
        Initialize the standard logger.

        Args:
            standard_rate: Rate for standard logging (seconds)
        """
        self.standard_rate = standard_rate
        self.data_frame = pd.DataFrame(
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
        self.mode_changed = False
        self.display_counter = 0  # Counter for display rate in high frequency mode

    def run(self, exit_event, data_queue, data_logger, sdl_mode):
        """
        Main thread function that processes and downsamples data.

        Args:
            exit_event: Threading event to signal thread termination
            data_queue: Queue containing data to be processed and logged
            data_logger: Logger instance for writing data
            sdl_mode: Shared object containing current mode (SDL_START value)
        """
        logging.info("Standard logging thread started")
        last_1hz_update = 0
        last_display_update = 0  # For display updates in high-frequency mode
        buffer_limit = 32  # Maximum buffer size for 32Hz to 1Hz conversion
        last_data = None
        last_mode = 0

        # Print current mode status
        print("\nRunning in STANDARD (1 Hz) MODE\n")

        while not exit_event.is_set():
            # Check if mode has changed
            current_mode = sdl_mode.value
            if current_mode != last_mode:
                last_mode = current_mode
                if current_mode > 0:
                    logging.info("Standard logger now in high-frequency support mode")
                    # Reset display timer to ensure immediate display update
                    last_display_update = 0
                    # Force data processing on next cycle
                    time_for_display = True
                else:
                    logging.info("Standard logger now in normal 1Hz display mode")
                    print("\nReturned to STANDARD (1 Hz) MODE\n")
                self.mode_changed = True
                self.display_counter = 0

            current_time = time.time()
            enough_data_for_1hz = self.data_frame.shape[0] >= buffer_limit
            time_for_1hz_update = (current_time - last_1hz_update) >= self.standard_rate
            # Check if it's time to update display in high frequency mode (every 1 second)
            time_for_display = (current_time - last_display_update) >= 1.0

            # Process incoming data (empty the queue)
            while not data_queue.empty():
                # Get data from queue
                data_array = data_queue.get()
                last_data = data_array  # Save for display

                # Add data to dataframe
                self.data_frame = concat_data(self.data_frame, data_array)

                # Maintain fixed size buffer by removing oldest data when exceeding limit
                if self.data_frame.shape[0] > buffer_limit:
                    self.data_frame = self.data_frame.iloc[-buffer_limit:]

            # Check if it's time to generate a 1Hz update
            if (
                time_for_1hz_update or (sdl_mode.value > 0 and time_for_display)
            ) and last_data is not None:
                try:
                    # Reset timestamp for next update
                    if time_for_1hz_update:
                        last_1hz_update = current_time
                    if time_for_display:
                        last_display_update = current_time

                    # Create a timestamp that's exactly on the second (truncate microseconds)
                    exact_second_timestamp = datetime.now().replace(microsecond=0)

                    # If we have enough data, use averaging, otherwise use latest value
                    if enough_data_for_1hz:
                        # Convert to datetime and resample to 1Hz
                        self.data_frame["TIME"] = pd.to_datetime(
                            self.data_frame["TIME"]
                        )
                        self.data_frame.set_index("TIME", inplace=True)
                        downsampled_data = self.data_frame.resample("1s").mean()

                        # Reset dataframe for next cycle
                        downsampled_data.reset_index(inplace=True)
                        self.data_frame.reset_index(inplace=True)

                        if not downsampled_data.empty:
                            # Create dictionary for log file writing
                            my_data = {
                                "tNow": exact_second_timestamp,
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
                            "tNow": exact_second_timestamp,
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

                    # Prepare data for logging (round values)
                    my_data_rounded = prepare_data_for_logging(my_data)

                    # Always display the data, but select the right mode indicator
                    current_mode_str = "32 Hz" if sdl_mode.value > 0 else "1 Hz"

                    # In 32Hz mode, only display every 1 second
                    if sdl_mode.value == 0 or time_for_display:
                        print(format_data_display(my_data_rounded, current_mode_str))
                        self.display_counter += 1

                    # Only write to the log file on 1Hz schedule in standard mode
                    # In high frequency mode, the high frequency logger handles writing
                    if time_for_1hz_update and sdl_mode.value == 0:
                        data_logger.write_logfile(my_data_rounded)

                except Exception as e:
                    # Using warning level to prevent flooding console
                    logging.warning(f"Error processing data for output: {e}")

            # Small sleep to prevent CPU hogging
            time.sleep(0.01)


class ModeMonitor:
    """
    Monitors and manages mode changes between standard and high frequency logging.
    """

    def __init__(self, host, port):
        """
        Initialize the mode monitor.

        Args:
            host: Host address for UDP socket
            port: Port for receiving commands
        """
        self.host = host
        self.port = port

    def setup_socket(self):
        """
        Set up UDP socket for receiving mode change commands.

        Returns:
            socket: Configured UDP socket
        """
        import socket

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_socket.bind((self.host, self.port))
        server_socket.setblocking(False)  # Non-blocking socket
        return server_socket

    def check_mode_command(self, server_socket, sdl_mode):
        """
        Check for incoming UDP commands to change the logging mode.

        Args:
            server_socket: UDP socket for receiving commands
            sdl_mode: Shared object for mode state

        Returns:
            bool: True if mode changed, False otherwise
        """
        import select
        import socket

        # Use select to check if there's data to read with a timeout
        try:
            readable, _, _ = select.select([server_socket], [], [], 0.001)

            if server_socket in readable:
                data, addr = server_socket.recvfrom(4096)
                command = data.decode().strip()

                # Check if it's a status request
                if command.upper() == "STATUS":
                    try:
                        # Try to send status back to the requestor
                        mode_str = "32Hz" if sdl_mode.value > 0 else "1Hz"
                        status_msg = f"CURRENT_MODE:{mode_str}"
                        response_socket = socket.socket(
                            socket.AF_INET, socket.SOCK_DGRAM
                        )
                        response_socket.sendto(status_msg.encode(), (self.host, 8251))
                        logging.info(
                            f"Status request received, responded with {status_msg}"
                        )
                    except Exception as e:
                        logging.warning(f"Error sending status response: {e}")
                    return False  # No mode change, just status request

                # Try to convert command to float for mode change
                try:
                    new_status = float(command)
                    if new_status != sdl_mode.value:
                        old_mode = "1 Hz" if sdl_mode.value == 0 else "32 Hz"
                        new_mode = "32 Hz" if new_status > 0 else "1 Hz"

                        # Clear screen for visibility
                        print("\033[2J\033[H")  # ANSI escape codes to clear screen
                        print("=" * 80)
                        print(f"MODE CHANGE DETECTED: {old_mode} -> {new_mode}")
                        print("=" * 80)

                        if new_status > 0:
                            print(
                                "\n*** SWITCHING TO HIGH FREQUENCY (32 Hz) MODE ***\n"
                            )
                        else:
                            print("\n*** SWITCHING BACK TO STANDARD (1 Hz) MODE ***\n")

                        # Update the shared mode value
                        sdl_mode.value = new_status
                        logging.info(f"Mode changed from {old_mode} to {new_mode}")

                        # No need to sleep here - this might block the main thread
                        return True
                except ValueError:
                    # Not a valid float command
                    logging.warning(f"Invalid command received: {command}")
                    pass
        except Exception as e:
            # No data or error reading
            logging.error(f"Error checking mode command: {e}")
            pass

        return False
