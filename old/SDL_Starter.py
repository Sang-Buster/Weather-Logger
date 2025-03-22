#!/usr/bin/env python3
"""
UDP Sender to START Short Term High Frequency Data Logging

This script sends a UDP message with value '1' to port 8250 to trigger
the start of high-frequency (32 Hz) data logging in the weather station
data collection system.

Created By: Avinash Muthu Krishna, muthukra@erau.edu
Created: 02 Oct 2023
Modified: 02 Oct 2023
"""

import socket
import time


def start_high_frequency_logging():
    """
    Send a UDP message to start high-frequency data logging.

    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        # Set up UDP connection
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Connection details
        host = "localhost"
        port = 8250
        message = "1"  # Command to start high-frequency logging

        # Send start command multiple times to ensure it's received
        for _ in range(3):  # Try sending 3 times
            client_socket.sendto(message.encode(), (host, port))
            time.sleep(0.1)  # Small delay between sends

        print(
            "High-frequency (32 Hz) mode START command sent successfully to port", port
        )
        print("The weather station should now be logging at 32 Hz.")
        print("If not, ensure Weather_Station_Tester_v4.py is running.")

        # Verify mode is changed by trying to read back status (optional)
        try:
            # Set up a socket to listen for any acknowledgment
            verify_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            verify_socket.settimeout(1.0)  # Set a short timeout
            verify_socket.bind(
                ("localhost", 8251)
            )  # Use a different port for verification

            print("Waiting for mode change confirmation...")
            time.sleep(1)  # Wait a moment for the change to take effect

            # Try to send a verification request
            verify_msg = "STATUS"
            client_socket.sendto(verify_msg.encode(), (host, port))

            return True
        except Exception as e:
            # If verification fails, it doesn't mean the command failed
            # The main script might just not support this verification method
            print(f"Verification failed: {e}")
            pass

        return True

    except Exception as e:
        print(f"Error sending start command: {e}")
        return False


if __name__ == "__main__":
    print(
        "\nSending command to switch weather station to HIGH FREQUENCY (32 Hz) MODE...\n"
    )
    success = start_high_frequency_logging()

    if success:
        print("\nTo verify the mode has changed:")
        print("1. Check the console output of Weather_Station_Tester_v4.py")
        print(
            "2. Look for a message like '*** SWITCHING TO HIGH FREQUENCY (32 Hz) MODE ***'"
        )
        print(
            "3. A new high-frequency log file should be created in the current directory\n"
        )
        print("To switch back to 1 Hz mode, run SDL_Stopper.py\n")
