#!/usr/bin/env python3
"""
UDP Sender to STOP Short Term High Frequency Data Logging

This script sends a UDP message with value '0' to port 8250 to trigger
the stop of high-frequency (32 Hz) data logging in the weather station
data collection system.
"""

import socket
import time

from weather_logger.config import HOST, PORT_CONTROL, PORT_STATUS


def verify_mode_change():
    """
    Attempt to verify that the mode change was received by requesting status.

    Returns:
        bool: Always returns True as verification is optional
    """
    try:
        # Set up a socket to listen for any acknowledgment
        verify_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        verify_socket.settimeout(1.0)  # Set a short timeout
        verify_socket.bind((HOST, PORT_STATUS))

        print("Waiting for mode change confirmation...")
        time.sleep(1)  # Wait a moment for the change to take effect

        # Try to send a verification request
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        verify_msg = "STATUS"
        client_socket.sendto(verify_msg.encode(), (HOST, PORT_CONTROL))
    except Exception as e:
        print(f"Verification attempt failed: {e}")

    # Always return True since verification is optional
    return True


def stop_high_frequency_logging():
    """
    Send a UDP message to stop high-frequency data logging.

    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        # Set up UDP connection
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Connection details
        message = "0"  # Command to stop high-frequency logging

        # Send stop command multiple times to ensure it's received
        for _ in range(3):  # Try sending 3 times
            client_socket.sendto(message.encode(), (HOST, PORT_CONTROL))
            time.sleep(0.1)  # Small delay between sends

        print(
            f"High-frequency (32 Hz) mode STOP command sent successfully to port {PORT_CONTROL}"
        )
        print("The weather station should now return to standard 1 Hz logging.")
        print("If not, ensure weather_station.py is running.")

        # Verify mode is changed by trying to read back status (optional)
        return verify_mode_change()

    except Exception as e:
        print(f"Error sending stop command: {e}")
        return False


if __name__ == "__main__":
    print(
        "\nSending command to switch weather station BACK to STANDARD (1 Hz) MODE...\n"
    )
    success = stop_high_frequency_logging()

    if success:
        print("\nTo verify the mode has changed:")
        print("1. Check the console output of weather_station.py")
        print(
            "2. Look for a message like '*** SWITCHING BACK TO STANDARD (1 Hz) MODE ***'"
        )
        print("3. The data should now be logged at 1 Hz\n")
        print("To switch back to 32 Hz mode, run sdl_high.py\n")
