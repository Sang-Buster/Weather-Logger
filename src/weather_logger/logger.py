#!/usr/bin/env python3
"""
Logging functionality for Weather Logger

This module handles logging of weather data to files with automatic rotation.
"""

import csv
import logging
import os
import queue
import socket
import sys
import threading
import time
from datetime import datetime


class DataLogger:
    """
    A class for managing long-duration logging with automatic file rotation.

    This class handles:
    - Creating and rotating log files at specified time intervals
    - Managing symbolic links to current and previous log files
    - Writing data dictionary entries to CSV files
    """

    def __init__(self, log_dir, fieldnames, strftime_str, do_flush=False):
        """
        Initialize the data logger.

        Args:
            log_dir (str): Directory where log files will be stored
            fieldnames (list): Column headers for the CSV file
            strftime_str (str): Format string for datetime to determine rotation frequency
            do_flush (bool, optional): Whether to flush after each write. Defaults to False.
        """
        logging.debug("DataLogger init")
        self.log_dir = log_dir
        self.fieldnames = fieldnames
        self.name_check_cnt = (
            0  # Name check counter (counts # of checks to see if name should change)
        )
        self.name_change_cnt = 0  # Name change counter
        self.err_cnt = 0  # Aggregate indicator of all warnings or errors
        self.strftime_str = strftime_str
        self.do_flush = do_flush  # Flush file every write? Yes for tail -f; no for storage longevity

        # Make sure base logfile dir exists and is writeable
        self.check_or_make_log_dir(log_dir)

        # Get IP address for debugging
        self.ip_addr_str = self.get_hostname_ip()

        # Open new logfile and report if it already exists (for restart condition)
        self.open_new_logfile_at_current_time()
        fname_start = self.fname_prefix  # Start logfile_name_updater() thread

        # Set up exit event and queue for thread communication
        self.e = threading.Event()  # Exit event for all threads
        self.q_fname = (
            queue.Queue()
        )  # Queue visible by all methods and logfile_name_updater() thread

        # Debug flag
        self.debug = 0  # Logfile writer debug flag

        # Start filename checker and rotator thread
        t2 = threading.Thread(
            name="logfile_name_updater",
            target=self.logfile_name_updater,
            args=(fname_start, self.q_fname, self.ip_addr_str),
        )
        t2.start()

    def check_or_make_log_dir(self, log_dir):
        """
        Check if log directory exists; create it if it doesn't.

        Args:
            log_dir (str): Directory path to check/create

        Returns:
            int: 0 on success
        """
        if not os.path.isdir(log_dir):
            logging.debug("[%s] not found! creating it...", log_dir)
            try:
                os.mkdir(log_dir)
                logging.debug("success.")
            except Exception as e:
                logging.debug("Error - could not create [%s]: %s", log_dir, e)
                sys.exit(-1)
        return 0

    def get_hostname_ip(self):
        """
        Get the local IP address.

        Returns:
            str: The IP address of the host
        """
        # Using UDP socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # connect() for UDP doesn't send packets
        s.connect(("10.0.0.0", 0))
        return s.getsockname()[0]

    def open_new_logfile_at_current_time(self):
        """
        Open a new log file with the current timestamp as part of the filename.

        Also creates/updates symbolic links to current and previous log files.
        """
        t_now_fname = datetime.now()
        self.fname_prefix = t_now_fname.strftime(self.strftime_str)

        # Create log filename with datetime prefix
        csv_name_log = os.path.join(
            self.log_dir, f"{self.fname_prefix}_weather_station_data.csv"
        )

        # Check if file exists (for resuming logging)
        self.file_exists = os.path.isfile(csv_name_log)

        # Open file for appending
        try:
            self.fd_log = open(csv_name_log, "a")
        except Exception as e:
            logging.debug("Unexpected error: %s", e)
            logging.debug(
                "Error occurred when trying to create a new logfile - check disk space"
            )
            sys.exit(-1)

        self.first_log_line = True  # Flag to write CSV header before first data
        logging.debug("\t%s: logging data to: %s", sys.argv[0], csv_name_log)

        # Create/update symbolic links for current and previous log files
        dst_prev = os.path.join(self.log_dir, "previous_weather_data_logfile.csv")
        dst_cur = os.path.join(self.log_dir, "current_weather_data_logfile.csv")

        # Remove previous symbolic link if it exists
        try:
            if os.path.exists(dst_prev):
                os.remove(dst_prev)
                logging.debug("\tremoved previous symbolic link: %s", dst_prev)
        except Exception as e:
            self.err_cnt += 1
            logging.debug(
                "Warning: err_cnt=%d, could not delete previous logfile symbolic link, %s --> %s: %s",
                self.err_cnt,
                csv_name_log,
                dst_prev,
                e,
            )

        # Rename current to previous symbolic link
        try:
            if os.path.exists(dst_cur):
                os.rename(dst_cur, dst_prev)
                logging.debug(
                    "\trenamed current to previous sym link: %s --> %s",
                    dst_cur,
                    dst_prev,
                )
        except Exception as e:
            self.err_cnt += 1
            logging.debug(
                "Warning: err_cnt=%d, could not rename prev to current logfile symlink, %s --> %s: %s",
                self.err_cnt,
                csv_name_log,
                dst_cur,
                e,
            )

        # Create new symbolic link for current log file
        try:
            os.symlink(csv_name_log, dst_cur)
            logging.debug(
                "\tnew current sym link created successfully: %s --> %s",
                csv_name_log,
                dst_cur,
            )
        except Exception as e:
            self.err_cnt += 1
            logging.debug(
                "Warning: err_cnt=%d, symbolic link failed! %s --> %s: %s",
                self.err_cnt,
                csv_name_log,
                dst_cur,
                e,
            )

    def logfile_name_updater(self, fname_start, q_fname, ip_addr_str):
        """
        Thread function that periodically checks if the logfile name should change.

        Runs continuously until exit event is set, checking if the formatted
        date/time has changed and should trigger a new logfile.

        Args:
            fname_start (str): Initial filename prefix to compare against
            q_fname (Queue): Queue for sending new filename messages
            ip_addr_str (str): IP address string for logging
        """
        if self.debug > 0:
            logging.debug("Starting logfile name checker and setter thread")

        fname_prefix = fname_start  # Initialize with starting filename

        while not self.e.is_set():
            t_now = datetime.now()  # Get current time
            fname_test = t_now.strftime(self.strftime_str)  # Format as string

            self.name_check_cnt += 1

            # If date/time format has changed, update filename
            if fname_prefix != fname_test:
                if self.debug > 0:
                    logging.debug("Time period changed - rotating log file!")

                fname_prefix = fname_test
                self.name_change_cnt += 1

                if self.debug > 0:
                    logging.debug(
                        "[%s], name_check_cnt=%d, name_change_cnt=%d, ip=%s sending new logfile prefix: [%s]",
                        t_now,
                        self.name_check_cnt,
                        self.name_change_cnt,
                        ip_addr_str,
                        fname_prefix,
                    )

                q_fname.put(fname_prefix)

            # Sleep before next check
            time.sleep(10)

    def write_logfile(self, data_dict):
        """
        Write data to the current logfile and check if filename rotation is needed.

        Args:
            data_dict (dict): Dictionary containing data to log with keys matching fieldnames
        """
        t_now = data_dict["tNow"]

        if self.debug > 1:
            logging.debug("[%s] writing to file [%s]", t_now, self.fd_log.name)

        # Check for filename prefix change (at midnight or whenever strftime_str changes)
        while not self.q_fname.empty():
            # Get message from queue (value not used, just triggers rotation)
            fname_prefix_unused = self.q_fname.get()
            self.name_change_cnt += 1

            if self.debug > 0:
                logging.debug(
                    "name_change_cnt=%d, rotating log file to new filename: [%s]",
                    self.name_change_cnt,
                    fname_prefix_unused,
                )
                logging.debug("closing current filename: [%s]", self.fd_log.name)

            # Close current file and open new one with updated name
            self.fd_log.close()

            if self.debug > 0:
                logging.debug("preparing new log file")

            self.open_new_logfile_at_current_time()

            if self.debug > 0:
                logging.debug(
                    "done. new logfile ready for writing: [%s]", self.fd_log.name
                )

        # Write CSV header if this is the first line in a new file
        if self.first_log_line:
            if self.debug > 0:
                logging.debug("logging fieldnames: %s", self.fieldnames)

            # Create CSV writer
            self.dw_log = csv.DictWriter(
                self.fd_log, fieldnames=self.fieldnames, delimiter=","
            )

            if self.debug > 0:
                logging.debug("logging data to: %s", self.fd_log.name)

            # Write header only for new files
            if not self.file_exists:
                self.dw_log.writeheader()
            else:
                if self.debug > 0:
                    logging.debug(
                        "logfile existed before open(), so did *not* write dictwriter field names"
                    )

            self.first_log_line = False  # Only write header once

        # Write data to CSV logfile
        try:
            self.dw_log.writerow(data_dict)
            if self.do_flush:
                self.fd_log.flush()  # Force write immediately instead of buffering
        except ValueError:
            print(
                "Error - if file opened properly, then you probably tried to write field names"
            )
            print("       that were inconsistent with your initialization, which was:")
            print(f"\tfieldnames={self.fieldnames}")
            print("fieldnames provided in data_dict:")
            for k, v in data_dict.items():
                print(f"\t{k}")
            print("make these match!\nexiting!")
            self.e.set()  # Signal threads to exit
            sys.exit(-2)
        except Exception as e:
            logging.debug("Unexpected error: %s", e)
            self.e.set()  # Signal threads to exit
            sys.exit(-1)

    def close(self):
        """
        Close the log file and ensure data is flushed.
        """
        try:
            self.fd_log.flush()
            self.fd_log.close()
            logging.debug("Log file closed: %s", self.fd_log.name)
        except Exception as e:
            logging.debug("Error closing log file: %s", e)
