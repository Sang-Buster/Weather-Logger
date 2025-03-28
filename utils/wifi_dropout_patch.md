# **Preventing Constant WiFi Dropouts on Raspberry Pi**

This guide provides steps to prevent **constant WiFi dropouts** on a Raspberry Pi by setting up **passwordless SSH, systemd services, WiFi auto-reconnect scripts, and static IP configuration**.

---

## **1. Setup Passwordless SSH on Raspberry Pi**
Run the following commands on your **Raspberry Pi**:

```sh
# Generate SSH key if you don't have one already
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519

# Copy the SSH key to the host machine (Energy Systems lab machine)
ssh-copy-id pi@host_machine_ip
```

Now, test passwordless login:

```sh
ssh pi@host_machine_ip
```

You should be able to log in without entering a password. This setup will be used for automated rsync operations.

---

## **2. Set Proper File Permissions on Host Machine**
On your **host machine**, ensure the Raspberry Pi has access to the shared directory:

```sh
sudo chown -R pi:pi /var/tmp/wx
```

---

## **3. Setup Systemd Service for Continuous Operation**
To ensure continuous operation of all services, create a systemd service file:

```sh
sudo cp utils/weather_logger.service /etc/systemd/system/weather_logger.service
```

Enable and start the service:

```sh
sudo systemctl daemon-reload
sudo systemctl enable weather_logger.service
sudo systemctl start weather_logger.service
```

You can check the status of these screen sessions at any time using:
```sh
screen -ls
```

And attach to any session using:
```sh
screen -r weather_logger    # for the weather logger
screen -r wifi_reconnect    # for the WiFi reconnect script
screen -r rsync_wx          # for the rsync script
```

---

## **4. Configure WiFi Settings**

### **4.1 Install Required Packages**
```sh
sudo apt update
sudo apt install -y wpasupplicant wireless-tools
```

### **4.2 Enable and Start wpa_supplicant Service**
```sh
sudo systemctl enable wpa_supplicant
sudo systemctl start wpa_supplicant
```

### **4.3 Configure wpa_supplicant**
Edit your **WiFi configuration file** at `/etc/wpa_supplicant/wpa_supplicant.conf`:

```sh
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
ap_scan=1

network={
    ssid="EagleNet"
    key_mgmt=NONE
    scan_ssid=1
    priority=100
    bgscan="simple:10:-70:300"  # Background scan every 10s if signal < -70dBm
    autoscan=periodic:10  # Force periodic scan every 10 seconds regardless of signal
    ap_max_scan_ssid=1  # Only scan for EagleNet
    ap_scan=1
    passive_scan=0  # Use active scanning
}
```

### **4.4 Apply WiFi Configuration**
```sh
# Stop the current WiFi service
sudo systemctl stop wpa_supplicant

# Kill any existing wpa_supplicant processes
sudo killall wpa_supplicant

# Start wpa_supplicant with the new configuration
sudo wpa_supplicant -B -i wlan1 -c /etc/wpa_supplicant/wpa_supplicant.conf

# Restart the wpa_supplicant service
sudo systemctl restart wpa_supplicant
```

### **4.5 Verify WiFi Status**
```sh
# Check wpa_supplicant status
sudo systemctl status wpa_supplicant

# Check WiFi connection status
sudo iwconfig wlan1

# Check WiFi signal strength
sudo iwconfig wlan1 | grep -i --color quality
```

This configuration:
- Connects to **EagleNet**.
- Uses **background scanning** to reconnect if the signal drops **below -70dBm**.
- Forces periodic scanning every 10 seconds.
- Uses active scanning for better reliability.

---

## **5. Assign a Secondary Static IP**
To improve network reliability, assign a **static IP** alongside DHCP:

```sh
sudo nmcli connection modify "EagleNet 1" ipv4.method auto
sudo nmcli connection modify "EagleNet 1" ipv4.addresses "10.33.229.250/17"
sudo nmcli connection modify "EagleNet 1" ipv4.gateway "10.33.255.254"
sudo nmcli connection modify "EagleNet 1" ipv4.dns "8.8.8.8,8.8.4.4"
sudo nmcli connection modify "EagleNet 1" ipv4.ignore-auto-dns no
sudo nmcli connection modify "EagleNet 1" ipv4.never-default no
```

### **Apply the changes:**
```sh
sudo nmcli connection up "EagleNet 1"
```

---

## **6. Persistent Static IP for wlan1**

This setup ensures `wlan1` keeps the static IP `10.33.229.250`, even if DHCP removes it.

### **Files Created:**
1. **Service:** `/etc/systemd/system/static-ip-wlan1.service`
2. **Timer:** `/etc/systemd/system/static-ip-wlan1.timer`

### **Service (`static-ip-wlan1.service`):**
```ini
[Unit]
Description=Ensure wlan1 keeps static IP
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/bin/bash -c "ip addr show wlan1 | grep -q '10.33.229.250' || ip addr add 10.33.229.250/17 dev wlan1"
RemainAfterExit=yes
Type=oneshot
```

### **Timer (`static-ip-wlan1.timer`):**
```ini
[Unit]
Description=Check and re-add static IP every 30 seconds

[Timer]
OnBootSec=10s
OnUnitActiveSec=30s
Unit=static-ip-wlan1.service

[Install]
WantedBy=multi-user.target
```

### **Enable & Start the Timer:**
```sh
sudo systemctl daemon-reload
sudo systemctl enable static-ip-wlan1.timer
sudo systemctl start static-ip-wlan1.timer
```

This will check and re-add the IP every 30 seconds.

---

## **7. Log WiFi Disconnections**
Enable debug-level logging for **NetworkManager** and **wpa_supplicant**:

```sh
# Enable NetworkManager debug logging
sudo nmcli general logging level DEBUG domains ALL

# Enable wpa_supplicant debug logging
sudo sed -i 's/#debug=0/debug=1/' /etc/wpa_supplicant/wpa_supplicant.conf
sudo systemctl restart wpa_supplicant
```

To **check logs**, use:

```sh
# Check NetworkManager logs
journalctl -u NetworkManager --no-pager | tail -50
```
