<div align="center">
  <img src="README.assets/logo.png" alt="Logo" width="15%">
  <h1 align="center">Weather Logger</h1>
</div>

A modular Python system for logging weather data from an RM Young 81000V Anemometer. This system is designed for researchers and weather monitoring applications, providing both real-time data collection and historical analysis capabilities. It's particularly well-suited for long-term environmental studies and meteorological research, offering flexible data collection modes and robust data management features.

<div align="center">

## ✨ Features

</div>

- Continuous 1 Hz logging for long-term data collection
- On-demand 32 Hz high-frequency logging triggered by UDP commands
- Automatic daily log file rotation with symbolic links for easy access
- UDP unicast/broadcast capabilities for real-time data streaming
- Automated rsync functionality for seamless data synchronization with remote servers

<div align="center">

## 🚀 Installation

</div>

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/erau-sangxing/Weather-Logger.git
cd Weather-Logger
```

Get [uv](https://docs.astral.sh/uv/getting-started/installation/) and install the dependencies:

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -r requirements.txt
```

<div align="center">

## 👉 Applications

</div>

The Raspberry Pi runs 3 applications in 3 screen sessions that are automatically started on boot:

1. `weather_logger`: Runs the main weather station application
2. `wifi_reconnect`: Monitors and maintains WiFi connectivity
3. `rsync_wx`: Syncs weather data to the Energy Systems lab machine every 30 seconds

For detailed information about these screen sessions and WiFi configuration, please refer to `utils/wifi_dropout_patch.md`.

You can check the status of these screen sessions at any time using:
```bash
screen -ls
```

And attach to any session using:
```bash
screen -r weather_logger  # for the weather logger
screen -r wifi_reconnect  # for the WiFi reconnect script
screen -r rsync_wx       # for the rsync script
```

<div align="center">

## 🛠 Usage

</div>

### 🏃 Manually Starting the Weather Logger

Run the main script to start the weather logger in standard 1 Hz mode:

```bash
uv run src/weather_station.py
```

### ⚡ Switching to High-Frequency Mode

To switch to high-frequency (32 Hz) logging, run:

```bash
uv run src/sdl_high.py # high-frequency serial data logger
```

### 🔄 Switching Back to Standard Mode

To switch back to standard (1 Hz) logging, run:

```bash
uv run src/sdl_low.py # low-frequency serial data logger
```

### 📄 Log Files

Log files are stored in `/var/tmp/wx/` by default, with the naming format:
- `YYYY_MM_DD_weather_station_data.csv`

The system also maintains symbolic links for easy access:
- `current_weather_data_logfile.csv` - Points to the current log file
- `previous_weather_data_logfile.csv` - Points to the previous log file

<div align="center">

## ⚙️ Configuration

</div>

This project uses environment variables for configuration. To set up:

1. Copy the example environment file:
   ```
   cp .env.example .env
   ```

2. Edit `.env` to match your environment:
   ```
   # Set the IP for your visualization server
   UDP_IP=ANOTHER_IP_ADDRESS
   
   # Configure serial port for your sensor
   SERIAL_PORT=/dev/ttyUSB0
   
   # Adjust data collection rates if needed
   HIGH_FREQ_RATE=32
   STANDARD_RATE=1
   ```

3. The `.env` file is excluded from git by the `.gitignore` file to keep sensitive information private.


<div align="center">

## 📁 Project Structure

</div>

```
📦weather_logger
 ┣ 📂README.assets                     // Assets for README documentation
 ┣ 📂old                               // Original scripts (for reference)
 ┃ ┣ 📄SDL_Starter.py
 ┃ ┣ 📄SDL_Stopper.py
 ┃ ┣ 📄Weather_Station_Tester_v4.py
 ┃ ┣ 📄daily_logfile_rotator.py
 ┃ ┗ 📄roundOnlyRoundableDictKeys.py
 ┣ 📂src                               // Refactored modular code
 ┃ ┣ 📂weather_logger                     // Core weather logger scripts
 ┃ ┃ ┣ 📄config.py                           // Configuration settings
 ┃ ┃ ┣ 📄data_processor.py                   // Data processing functions
 ┃ ┃ ┣ 📄display.py                          // Display formatting utilities
 ┃ ┃ ┣ 📄logger.py                           // Logging functionality
 ┃ ┃ ┣ 📄serial_handler.py                   // Serial communication handler
 ┃ ┃ ┣ 📄threads.py                          // Thread management classes
 ┃ ┃ ┣ 📄udp_sender.py                       // UDP sender for data transmission
 ┃ ┃ ┗ 📄utils.py                            // General utility functions
 ┃ ┣ 📄sdl_high.py                        // Starts high-frequency logging
 ┃ ┣ 📄sdl_low.py                         // Stops high-frequency logging
 ┃ ┗ 📄weather_station.py                 // Main script to run weather station
 ┣ 📂utils                             // Utility scripts for Raspberry Pi
 ┃ ┣ 📄metadata.yml                       // Metadata for weather data
 ┃ ┣ 📄rsync_var_tmp_wx.sh                // Rsync command to sync /var/tmp/wx to host
 ┃ ┣ 📄start_weather_logger.sh            // Starts the weather logger in a screen session
 ┃ ┣ 📄wifi_auto_reconnect.sh             // Auto reconnects to WiFi when disconnected
 ┃ ┗ 📄wifi_dropout_patch.md              // WiFi dropout patch
 ┣ 📄.env                              // Environment variables (ignored in Git)
 ┣ 📄.env.example                      // Example environment variable file
 ┣ 📄.gitignore                        // Git ignore file to exclude unnecessary files
 ┣ 📄LICENSE                           // License for the project
 ┣ 📄README.md                         // Documentation for the project
 ┗ 📄requirements.txt                  // Python dependencies
```

<div align="center">

## 👥 Credits

</div>

Original created by:
- Avinash Muthu Krishna, muthukra@erau.edu

Modified by:
- Erik Liebergall, lieberge@my.erau.edu
- Marc Compere, comperem@erau.edu
- Sang Xing, xingsang@erau.edu