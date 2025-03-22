#!/usr/bin/env python3
"""
Daily Logfile Rotator

A module that allows long-duration Python programs to log to filenames that
rotate every day (or minute or month) with the new date as prefix.

The longDurationLogger class also updates two symbolic links:
- current_weather_data_logfile.csv: Points to the current logfile
- previous_weather_data_logfile.csv: Points to the previous logfile

These symbolic links facilitate plot creation of the last 24 hours of weather
data that spans 2 files.

Usage tips:
- For testing, set strftimeStr to change every minute ('%Y_%m_%d__%H_%M')
- For production, set strftimeStr to change every day ('%Y_%m_%d')
- Choose whether to use fdLog.flush() based on your data logging rate
  (prefer not for fast logging; use for slow logging with tail -f monitoring)

Copyright 2023-2024 Marc Compere
Licensed under GNU General Public License version 3
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

logging.basicConfig(
    level=logging.DEBUG, format="[%(levelname)s] [%(threadName)-10s] %(message)s"
)


class longDurationLogger:
    """
    A class for managing long-duration logging with automatic file rotation.

    This class handles:
    - Creating and rotating log files at specified time intervals
    - Managing symbolic links to current and previous log files
    - Writing data dictionary entries to CSV files
    """

    def __init__(self, log_dir, fieldnames, strftime_str, do_flush=False):
        """
        Initialize the long duration logger.

        Args:
            log_dir (str): Directory where log files will be stored
            fieldnames (list): Column headers for the CSV file
            strftime_str (str): Format string for datetime to determine rotation frequency
            do_flush (bool, optional): Whether to flush after each write. Defaults to False.
        """
        logging.debug("longDurationLogger init")
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

        # Debug flags
        debug_log_rot = 1  # Logfile name rotator thread debug flag
        self.debug = 1  # Logfile writer debug flag

        logging.debug(
            "longDurationLogger() constructor: self.do_flush=%s, debug_log_rot=%s, self.debug=%s",
            self.do_flush,
            debug_log_rot,
            self.debug,
        )

        # Start filename checker and rotator thread
        t2 = threading.Thread(
            name="logfile_name_updater",
            target=self.logfile_name_updater,
            args=(fname_start, self.q_fname, self.ip_addr_str, debug_log_rot),
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
                dst_prev,
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
            logging.debug("\n\tis another data listener running? --> ~/stop_all.sh")
            logging.debug("         sys.exec_info: %s", sys.exc_info()[0])

    def logfile_name_updater(self, fname_start, q_fname, ip_addr_str, debug):
        """
        Thread function that periodically checks if the logfile name should change.

        Runs continuously until exit event is set, checking if the formatted
        date/time has changed and should trigger a new logfile.

        Args:
            fname_start (str): Initial filename prefix to compare against
            q_fname (Queue): Queue for sending new filename messages
            ip_addr_str (str): IP address string for logging
            debug (int): Debug level (0/1)
        """
        if debug > 0:
            logging.debug("Starting logfile name checker and setter thread")

        fname_prefix = fname_start  # Initialize with starting filename

        while not self.e.is_set():
            t_now = datetime.now()  # Get current time
            fname_test = t_now.strftime(self.strftime_str)  # Format as string

            if debug > 0:
                logging.debug(" ")
                logging.debug("fname_prefix = [%s]", fname_prefix)
                logging.debug("fname_test   = [%s]", fname_test)

            self.name_check_cnt += 1

            # If date/time format has changed, update filename
            if fname_prefix != fname_test:
                if debug > 0:
                    logging.debug("\n\n\n\n\n\n")
                    logging.debug("    Time period changed - rotating log file!")

                fname_prefix = fname_test
                self.name_change_cnt += 1

                if debug > 0:
                    logging.debug(
                        "[%s], name_check_cnt=%d, name_change_cnt=%d, ip=%s sending new logfile prefix: [%s]",
                        t_now,
                        self.name_check_cnt,
                        self.name_change_cnt,
                        ip_addr_str,
                        fname_prefix,
                    )

                q_fname.put(fname_prefix)

                if debug > 0:
                    logging.debug("\n\n\n\n\n\n")
            else:
                if debug > 0:
                    logging.debug(
                        "Checked, but no logfile name change needed, name_check_cnt=%d, name_change_cnt=%d",
                        self.name_check_cnt,
                        self.name_change_cnt,
                    )

            # Sleep before next check
            time.sleep(10)

        logging.debug("Thread exiting")

    def writeLogfile(self, data_dict):
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
                    "\n\n\n\tname_change_cnt=%d, rotating log file to new filename: [%s]",
                    self.name_change_cnt,
                    fname_prefix_unused,
                )
                logging.debug("\tclosing current filename: [%s]", self.fd_log.name)

            # Close current file and open new one with updated name
            self.fd_log.close()

            if self.debug > 0:
                logging.debug("\tpreparing new log file")

            self.open_new_logfile_at_current_time()

            if self.debug > 0:
                logging.debug(
                    "\tdone. new logfile ready for writing: [%s]", self.fd_log.name
                )
                logging.debug("\n\n\n")

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
                    logging.debug(
                        "--> assuming this is a restarted logger script appending to an existing logfile"
                    )

            if self.debug > 0:
                logging.debug("data logging fieldnames: %s", self.fieldnames)

            self.first_log_line = False  # Only write header once

        # Write data to CSV logfile
        try:
            self.dw_log.writerow(data_dict)
            if self.do_flush:
                self.fd_log.flush()  # Force write immediately instead of buffering
        except Exception as e:
            print("\n\n")
            print(f"Error encountered writing to log file: {e}")
            self.e.set()  # Signal threads to exit
            sys.exit(-1)


# Example usage when run as main script
if __name__ == "__main__":
    import random
    from datetime import datetime

    from daily_logfile_rotator import longDurationLogger as ldl

    logging.basicConfig(
        level=logging.DEBUG, format="[%(levelname)s] [%(threadName)-10s] %(message)s"
    )

    loop_cnt = 0
    t_start = time.time()
    debug = 1  # Main's debug flag
    dt = 2  # Loop delay in seconds
    skip_nth = 1000  # Print every N'th counter value
    e = threading.Event()  # Exit event

    # For testing, use minute rotation; for production use daily rotation
    strftime_str = "%Y_%m_%d__%H_%M"  # Changes every minute for testing
    # strftime_str = '%Y_%m_%d'        # Changes every day for production

    log_dir = "/var/tmp/wx"
    fieldnames = ["tNow", "Temp_C", "Pressure_Pa", "RH"]
    do_flush = False  # Set to True if using tail -f to monitor

    # Create logger instance
    my_ldl = ldl(log_dir, fieldnames, strftime_str, do_flush)

    try:
        logging.debug("Starting data collector example loop")

        if debug > 0:
            logging.debug(
                "%s listening... loop_cnt=%d, ip_addr_str=%s",
                sys.argv[0],
                loop_cnt,
                my_ldl.ip_addr_str,
            )

        # Main logging loop
        while not e.is_set():
            # Print counter with reduced terminal scrolling
            if (loop_cnt % skip_nth) == 0:
                logging.debug(
                    "[%s] long running process count %d", my_ldl.ip_addr_str, loop_cnt
                )
            else:
                print("%d," % loop_cnt, flush=True, end="")

            loop_cnt += 1

            # Generate random sample data
            temperature = random.uniform(0.0, 50.0)  # (deg C)
            pressure = random.uniform(1013.05, 1013.50)  # (hPa)/(mBar)
            humidity = random.uniform(40, 100)  # (%)
            t_now = datetime.now()

            # Create data dictionary
            data_dict = {
                "tNow": t_now,
                "Temp_C": temperature,
                "Pressure_Pa": pressure,
                "RH": humidity,
            }

            if debug > 1:
                for k, v in data_dict.items():
                    print("%s=%s" % (k, v))

            # Write data to logfile
            my_ldl.writeLogfile(data_dict)

            # Wait before next iteration
            time.sleep(dt)

    except KeyboardInterrupt:
        logging.debug("Caught KeyboardInterrupt, closing logfile and exiting!")
        e.set()  # Signal all threads to exit
        my_ldl.e.set()  # Signal logger threads to exit
        my_ldl.fd_log.close()  # Close log file

        logging.debug("End time: %s", time.ctime())
        elapsed_time = time.time() - t_start
        logging.debug(
            "\n\nExiting after loop_cnt=%d, elapsed_time=%d seconds, name_check_cnt=%d, name_change_cnt=%d",
            loop_cnt,
            elapsed_time,
            my_ldl.name_check_cnt,
            my_ldl.name_change_cnt,
        )
