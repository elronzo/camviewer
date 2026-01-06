# INSTALL.md

This document describes a manual (but reproducible) installation of **CamViewer** on Raspberry Pi OS.

It assumes:
- Raspberry Pi OS (Bookworm / Trixie)
- user account: `ronzo` (adjust paths if different)
- you cloned this repository onto the target Pi
- HDMI-CEC is enabled on the TV (Samsung: AnyNet+)

---

## 1. Packages

Install the required packages:

```bash
sudo apt update
sudo apt install -y ffmpeg cec-utils socat
```

Notes:
- `ffplay` is part of `ffmpeg`
- `cec-ctl` is part of `cec-utils`
- `socat` is used for simple Unix-socket testing

---

## 2. Copy files into their runtime locations

From the repository root:

```bash
# scripts
sudo install -d -m 0755 /home/ronzo/scripts
sudo install -m 0755 scripts/cam-switcher.py /home/ronzo/scripts/cam-switcher.py

# CEC daemon
sudo install -m 0755 bin/ipcams-cec-daemon.py /usr/local/bin/ipcams-cec-daemon.py

# systemd units
sudo install -m 0644 systemd/cam-switcher.service /etc/systemd/system/cam-switcher.service
sudo install -m 0644 systemd/ipcams-cec-daemon.service /etc/systemd/system/ipcams-cec-daemon.service
sudo install -m 0644 systemd/clear-tty1.service /etc/systemd/system/clear-tty1.service
```

---

## 3. Configure RTSP credentials and camera settings

Create the local environment file (do **not** commit secrets):

```bash
sudo cp env/rtsp.env.example /home/ronzo/scripts/rtsp.env
sudo nano /home/ronzo/scripts/rtsp.env
```

Minimum variables (example):

```ini
RTSP_USER=admin
RTSP_PASS=CHANGE_ME
RTSP_DOMAIN=lan
RTSP_PORT=554
RTSP_PATH=/h264Preview_01_sub
```

Camera list is defined in `scripts/cam-switcher.py` (e.g. `front`, `garden`, `livingroom`, `cellar`).
Adjust hostnames/paths to match your camera models.

---

## 4. HDMI-CEC device name

The TV-facing HDMI-CEC name is configured in the daemon unit:

- `systemd/ipcams-cec-daemon.service`
  - `CEC_OSD_BASE=Cams`  (change to whatever you want the TV to show)

After editing units, always run:

```bash
sudo systemctl daemon-reload
```

---

## 5. Enable and start services

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ipcams-cec-daemon.service
sudo systemctl enable --now cam-switcher.service
sudo systemctl enable --now clear-tty1.service
```

---

## 6. Verify

### 6.1 Services are running

```bash
systemctl status ipcams-cec-daemon.service --no-pager
systemctl status cam-switcher.service --no-pager
```

### 6.2 Runtime directory and sockets

Both services use `/run/ipcams/` (created by systemd `RuntimeDirectory=`):

```bash
ls -l /run/ipcams
```

You should typically see:
- `cam-switch.sock`
- `ipcams-cec.sock` (daemon socket)

### 6.3 CEC traffic

```bash
sudo cec-ctl -d /dev/cec0 --monitor
```

Press ⏩ / ⏪ on the TV remote and confirm that `USER_CONTROL_PRESSED` events appear.

### 6.4 Manual camera switching (socket test)

```bash
printf "next\n" | socat - UNIX-CONNECT:/run/ipcams/cam-switch.sock
printf "prev\n" | socat - UNIX-CONNECT:/run/ipcams/cam-switch.sock
```

---

## 7. Troubleshooting

### “Permission denied: /run/user/1000 …”
Do not use `/run/user/<uid>` for sockets in headless/kiosk mode. This project uses `/run/ipcams` via `RuntimeDirectory=` to avoid logind dependencies.

### TV does not send keypresses
- Verify HDMI-CEC is enabled on TV (Samsung: AnyNet+).
- Some TVs only forward keys on specific HDMI ports.
- Try a different HDMI port (avoid “DVI” labeled ports if they behave differently).

### TV input gets stolen back to CamViewer
This happens if the daemon repeatedly sends **Active Source** (`0x82`) or **Image View On** (`0x04`).
CamViewer should send those at most once on startup (if at all), then use polite keepalive only.

### Boot log text flashes during switching
Mitigations:
- keep `StandardOutput=null` in `cam-switcher.service`
- optionally reduce systemd boot status output via kernel cmdline: `systemd.show_status=0 quiet loglevel=3`
- `clear-tty1.service` clears tty1 once after boot

---

## 8. Uninstall

```bash
sudo systemctl disable --now cam-switcher.service ipcams-cec-daemon.service clear-tty1.service
sudo rm -f /etc/systemd/system/cam-switcher.service
sudo rm -f /etc/systemd/system/ipcams-cec-daemon.service
sudo rm -f /etc/systemd/system/clear-tty1.service
sudo systemctl daemon-reload

sudo rm -f /usr/local/bin/ipcams-cec-daemon.py
sudo rm -f /home/ronzo/scripts/cam-switcher.py
sudo rm -f /home/ronzo/scripts/rtsp.env
```
