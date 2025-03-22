#!/usr/bin/env python3
"""
Serial handling for Weather Logger

This module handles serial communication with the RM Young 81000V Anemometer.
"""

import logging

import serial

from .utils import clean_sensor_value, generate_simulated_data


class SerialHandler:
    """
    Handles serial communication with the RM Young 81000V Anemometer.
    """

    def __init__(self, port, baudrate, timeout):
        """
        Initialize the serial handler.

        Args:
            port: Serial port path
            baudrate: Baud rate for serial communication
            timeout: Timeout for serial read operations
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.error_count = 0
        self.serial = None

        try:
            self.serial = serial.Serial(port, baudrate, timeout=timeout)
            logging.info(f"Successfully connected to serial port {port}")
        except Exception as e:
            logging.warning(f"Failed to open serial port: {e}")
            logging.info("Using simulated data mode")
            self.serial = None

    def __enter__(self):
        """
        Context manager entry point.

        Returns:
            self: The SerialHandler instance
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit point.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        self.close()
        return False  # Don't suppress exceptions

    def read_data(self):
        """
        Read data from the serial port or generate simulated data.

        Returns:
            tuple: (success, values) where success is a boolean and values is a list of data
        """
        try:
            if self.serial is not None:
                # Read from actual serial port
                data = self.serial.read_until(b"\r")

                try:
                    # Clean the data before decoding
                    data_clean = data.replace(b"\x00", b"")  # Remove null bytes
                    data_decoded = data_clean.decode().strip()
                    values = data_decoded.split()

                    # Validate that we have enough data points
                    if len(values) < 12:
                        # Too few values, use simulated data
                        self.error_count += 1
                        return False, generate_simulated_data()

                    # Clean each value
                    cleaned_values = [clean_sensor_value(val) for val in values]
                    return True, cleaned_values

                except UnicodeDecodeError:
                    self.error_count += 1
                    return False, generate_simulated_data()
                except Exception:
                    self.error_count += 1
                    return False, generate_simulated_data()
            else:
                # Generate simulated data when no serial connection
                return True, generate_simulated_data()

        except Exception:
            self.error_count += 1
            return False, generate_simulated_data()

    def close(self):
        """
        Close the serial connection.
        """
        if self.serial is not None:
            self.serial.close()
            logging.info(f"Serial port {self.port} closed")

    def get_error_count(self):
        """
        Get the current error count.

        Returns:
            int: Number of errors encountered during serial operations
        """
        return self.error_count
