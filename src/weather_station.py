#!/usr/bin/env python3
"""
Weather Station Data Logger for RM Young 81000V Anemometer
"""

import logging
import multiprocessing
import os
import queue
import threading
import time

import serial

from weather_logger.config import (
    DEBUG,
    DO_FLUSH,
    FIELDNAMES,
    HIGH_FREQ_RATE,
    HOST,
    LOG_DIR,
    PORT_CONTROL,
    SERIAL_BAUDRATE,
    SERIAL_PORT,
    SERIAL_TIMEOUT,
    STANDARD_RATE,
    STRFTIME_STR,
    UDP_IP,
    UDP_PORT,
)
from weather_logger.data_processor import process_raw_data
from weather_logger.display import print_welcome_message
from weather_logger.logger import DataLogger
from weather_logger.serial_handler import SerialHandler
from weather_logger.threads import HighFrequencyLogger, ModeMonitor, StandardLogger
from weather_logger.udp_sender import UDPSender


def main():
    """
    Main function to initialize threads and process sensor data.
    """
    # Set logging level based on DEBUG config
    if DEBUG > 0:
        logging.getLogger().setLevel(logging.INFO)
        if DEBUG > 1:
            logging.getLogger().setLevel(logging.DEBUG)

    # Record start time
    t_start = time.time()

    # Create shared value for SDL mode
    sdl_mode = multiprocessing.Value("d", 0.0)  # Use a double to store SDL_START value

    # Initialize the serial handler
    serial_handler = SerialHandler(SERIAL_PORT, SERIAL_BAUDRATE, SERIAL_TIMEOUT)

    # Initialize the data logger
    data_logger = DataLogger(LOG_DIR, FIELDNAMES, STRFTIME_STR, DO_FLUSH)

    # Create exit event and data queues
    exit_event = threading.Event()
    queue_high_freq = queue.Queue(
        maxsize=1000
    )  # Increased queue size for high frequency logging
    queue_standard = queue.Queue(
        maxsize=500
    )  # Increased queue size for standard frequency logging
    queue_visualization = queue.Queue(maxsize=500)  # Queue for visualization data

    # Create file lock for thread-safe file operations
    file_lock = threading.Lock()

    # Initialize thread objects
    high_freq_logger = HighFrequencyLogger(HIGH_FREQ_RATE)
    standard_logger = StandardLogger(STANDARD_RATE)
    mode_monitor = ModeMonitor(HOST, PORT_CONTROL)

    # Create UDP socket for command monitoring
    control_socket = mode_monitor.setup_socket()

    # Initialize UDP sender for visualization (if enabled)
    udp_sender = None
    if True:  # Always initialize UDP sender regardless of flag
        udp_sender = UDPSender(UDP_IP, UDP_PORT)
        udp_sender.start(queue_visualization)
        logging.info(
            f"UDP visualization sender started, sending to {UDP_IP}:{UDP_PORT}"
        )

    # Create and start threads
    high_freq_thread = threading.Thread(
        target=high_freq_logger.run,
        args=(exit_event, queue_high_freq, file_lock, data_logger, sdl_mode),
        name="HighFreqLogger",
    )

    standard_thread = threading.Thread(
        target=standard_logger.run,
        args=(exit_event, queue_standard, data_logger, sdl_mode),
        name="StandardLogger",
    )

    high_freq_thread.start()
    standard_thread.start()

    # Print welcome message
    print_welcome_message(LOG_DIR)

    try:
        # Track timing for rate control
        last_data_time = time.time()

        # Set initial collection rate (in seconds per reading)
        data_interval = STANDARD_RATE / 10  # Default to 10Hz collection for 1Hz output

        # Periodically check mode indicator (at most every 5 seconds)
        mode_check_time = time.time()
        mode_check_interval = 5.0  # seconds

        # Keep track of mode for changes
        last_mode = 0
        sample_count = 0
        data_points_count = 0

        while True:
            # Check for UDP commands to change mode
            current_time = time.time()

            try:
                # Check for mode changes (non-blocking)
                mode_monitor.check_mode_command(control_socket, sdl_mode)

                # Adjust data collection rate if mode changed
                current_mode = sdl_mode.value
                if current_mode != last_mode:
                    if current_mode > 0:
                        data_interval = HIGH_FREQ_RATE
                        logging.info(
                            "MAIN: Switching to high frequency (32 Hz) data collection"
                        )
                    else:
                        data_interval = STANDARD_RATE / 10
                        logging.info(
                            "MAIN: Switching to standard (1 Hz) data collection"
                        )

                    # Reset counters on mode change
                    sample_count = 0
                    data_points_count = 0
                    last_mode = current_mode

            except Exception as e:
                logging.error(f"Error in mode checking: {e}")
                # Continue to keep the main loop going

            # Periodically display current mode (helpful for troubleshooting)
            if current_time - mode_check_time > mode_check_interval:
                mode_str = (
                    "HIGH FREQUENCY (32 Hz)"
                    if sdl_mode.value > 0
                    else "STANDARD (1 Hz)"
                )
                logging.info(
                    f"Current mode: {mode_str}, processed {data_points_count} data points in last interval"
                )
                mode_check_time = current_time
                data_points_count = 0  # Reset counter for next interval

            # Wait until it's time for the next sample
            time_since_last = current_time - last_data_time
            if time_since_last < data_interval:
                sleep_time = data_interval - time_since_last
                # Use shorter sleep to improve responsiveness
                time.sleep(min(0.001, sleep_time))
                continue

            # Read data from serial port or generate simulated data
            try:
                success, values = serial_handler.read_data()
                last_data_time = time.time()  # Update last read time
                sample_count += 1

                # Process the raw data
                processed_values, _ = process_raw_data(
                    values, serial_handler.get_error_count()
                )

                # Add data to both queues, but don't block if queue is full
                try:
                    # Only add to high frequency queue when in high frequency mode
                    if sdl_mode.value > 0:
                        try:
                            queue_high_freq.put(processed_values, block=False)
                            data_points_count += 1
                        except queue.Full:
                            # If high frequency queue is full, try to clear it
                            try:
                                while not queue_high_freq.empty():
                                    queue_high_freq.get_nowait()
                                # Then try again
                                queue_high_freq.put(processed_values, block=False)
                                data_points_count += 1
                                logging.info(
                                    "High frequency queue cleared and new data added"
                                )
                            except Exception as e:
                                logging.warning(
                                    f"High frequency queue handling error: {e}"
                                )
                                logging.warning(
                                    "High frequency queue full, skipping data point"
                                )

                    # Always add to standard queue for display
                    queue_standard.put(processed_values, block=False)

                    # Always add to visualization queue (without conditional check)
                    try:
                        queue_visualization.put(processed_values, block=False)
                    except queue.Full:
                        # If visualization queue is full, clear it and try again
                        try:
                            while not queue_visualization.empty():
                                queue_visualization.get_nowait()
                            # Then try again
                            queue_visualization.put(processed_values, block=False)
                            logging.debug(
                                "Visualization queue cleared and new data added"
                            )
                        except Exception as e:
                            logging.warning(f"Visualization queue handling error: {e}")

                except queue.Full:
                    # Skip this data point for standard queue if full
                    logging.warning("Standard queue full, skipping data point")
                except Exception as e:
                    logging.error(f"Unexpected error handling data queues: {e}")

                # Log sampling rate occasionally for debugging
                if sample_count % 100 == 0 and DEBUG > 0:
                    logging.info(
                        f"Processed {sample_count} samples, current rate: {1.0 / data_interval:.2f} Hz"
                    )

            except serial.SerialException as e:
                logging.error(f"Serial port error: {e}")
                time.sleep(0.1)  # Longer pause on serial error
            except Exception as e:
                logging.error(f"Error reading or processing data: {e}")
                time.sleep(0.01)  # Brief pause on error

    except KeyboardInterrupt:
        print("\nCaught KeyboardInterrupt, closing logfiles and exiting!")
        exit_event.set()  # Signal threads to exit
        data_logger.e.set()  # Tell data logger threads to exit

        # Make sure all files are properly closed
        data_logger.close()
        serial_handler.close()

        # Stop UDP sender if running
        if udp_sender:
            udp_sender.stop()

        print(f"\nEnd time: {time.ctime()}")
        elapsed_time = time.time() - t_start  # Calculate elapsed time
        print(f"Exiting after running for {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    # Clear terminal for a clean start
    os.system("clear")
    main()
