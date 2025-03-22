#!/usr/bin/env python3
"""
UDP Sender for Weather Logger

This module sends weather data via UDP to a remote visualization server.
Supports both unicast and broadcast modes.
"""

import json
import logging
import os
import socket
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] [%(threadName)-10s] [%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)


class UDPSender:
    """Handles sending weather data via UDP to a remote visualization server."""

    def __init__(self, target_ip, target_port=5555, broadcast=False):
        """
        Initialize the UDP sender.

        Args:
            target_ip (str): IP address of the target visualization server
            target_port (int): UDP port to send data to
            broadcast (bool): Whether to use broadcast mode
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.broadcast = broadcast
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Enable broadcast if requested
        if broadcast:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            logging.info("UDP broadcast mode enabled")

        self.exit_event = threading.Event()
        self.data_queue = None
        self.sender_thread = None
        logging.info(f"UDP sender initialized, target: {target_ip}:{target_port}")

    def start(self, data_queue):
        """
        Start the UDP sender thread.

        Args:
            data_queue: Queue containing weather data to send
        """
        self.data_queue = data_queue
        self.sender_thread = threading.Thread(
            target=self._sender_loop, name="UDPSender", daemon=True
        )
        self.sender_thread.start()
        logging.info("UDP sender thread started")

    def stop(self):
        """Stop the UDP sender thread."""
        self.exit_event.set()
        if self.sender_thread and self.sender_thread.is_alive():
            self.sender_thread.join(timeout=1)
        self.socket.close()
        logging.info("UDP sender stopped")

    def _sender_loop(self):
        """Main loop that sends data from the queue to the remote server."""
        logging.info(
            f"UDP sender loop running, sending to {self.target_ip}:{self.target_port}"
        )
        last_sent_time = 0
        min_interval = 0.1  # Minimum interval between sends (seconds)
        packet_count = 0
        last_log_time = time.time()

        while not self.exit_event.is_set():
            try:
                # Check if it's time to send another data point (rate limiting)
                current_time = time.time()
                if current_time - last_sent_time < min_interval:
                    time.sleep(0.01)
                    continue

                # Get data from queue (non-blocking)
                if self.data_queue and not self.data_queue.empty():
                    data_point = self.data_queue.get(block=False)
                    packet_count += 1

                    # Convert data for transmission
                    data_to_send = self._format_data(data_point)

                    # Send via UDP
                    self.socket.sendto(data_to_send, (self.target_ip, self.target_port))
                    last_sent_time = current_time

                    # Log stats periodically
                    if current_time - last_log_time >= 10:
                        actual_rate = packet_count / (current_time - last_log_time)
                        logging.info(
                            f"[INFO] Current send rate: {actual_rate:.2f} Hz (sent {packet_count} packets in last 10s)"
                        )
                        packet_count = 0
                        last_log_time = current_time
                else:
                    # No data to send, brief sleep
                    time.sleep(0.01)

            except Exception as e:
                logging.error(f"Error in UDP sender: {e}")
                time.sleep(0.1)  # Brief pause on error

    def _format_data(self, data_point):
        """
        Format data for UDP transmission.

        Args:
            data_point: Raw data point from the queue

        Returns:
            bytes: Encoded data ready for transmission
        """
        # Extract timestamp and data values
        timestamp = data_point[0]

        # Create a dictionary with labeled data
        data_dict = {
            "timestamp": timestamp.isoformat()
            if isinstance(timestamp, datetime)
            else str(timestamp),
            "u_m_s": float(data_point[1]),
            "v_m_s": float(data_point[2]),
            "w_m_s": float(data_point[3]),
            "speed_2d": float(data_point[4]),
            "speed_3d": float(data_point[5]),
            "azimuth": float(data_point[6]),
            "elevation": float(data_point[7]),
            "pressure": float(data_point[8]),
            "temperature": float(data_point[9]),
            "humidity": float(data_point[10]),
            "sonic_temp": float(data_point[11]),
            "error": float(data_point[12]),
        }

        # Convert to JSON and encode as bytes
        return json.dumps(data_dict).encode("utf-8")


def get_config():
    """Get configuration from either command line or environment variables."""
    # Try to get config from environment variables first
    try:
        load_dotenv()
        return (
            os.getenv("UDP_IP", "127.0.0.1"),
            int(os.getenv("UDP_PORT", "5555")),
            os.getenv("UDP_BROADCAST", "false").lower() == "true",
        )
    except Exception as e:
        logging.warning(f"Could not load environment variables, using defaults: {e}")
        return "127.0.0.1", 5555, False


def main():
    """Main entry point for the UDP sender."""
    target_ip, target_port, broadcast = get_config()

    # Create and start sender
    sender = UDPSender(target_ip, target_port, broadcast)
    sender.start()


if __name__ == "__main__":
    main()
