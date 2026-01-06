# CamViewer

CamViewer is a Raspberry Pi–based fullscreen RTSP IP camera viewer controlled via
HDMI-CEC using the TV remote.

It is designed as a kiosk-style appliance:
- no desktop environment
- no mouse or keyboard required
- stable fullscreen video via ffplay
- camera switching via standard TV remote keys (CEC)

The project deliberately avoids heavy frameworks and behaves like a real HDMI
playback device so that TVs (especially Samsung models) recognize it properly.

---

## Features

- Fullscreen, low-latency RTSP playback (ffplay)
- Camera switching via TV remote (HDMI-CEC)
- Works on Raspberry Pi OS (Bookworm / Trixie)
- systemd-managed services
- Clean separation between player logic, HDMI-CEC handling and configuration
- No secrets committed to git

---

## Architecture Overview

```
TV Remote (HDMI-CEC)
        |
        v
+-----------------------------+
| ipcams-cec-daemon.py        |
|  - registers HDMI OSD name  |
|  - listens for CEC keys     |
|  - translates to commands   |
+-------------+---------------+
              |
              | Unix socket (/run/ipcams)
              v
+-----------------------------+
| cam-switcher.py             |
|  - manages ffplay           |
|  - switches RTSP streams    |
|  - runs fullscreen on tty1  |
+-------------+---------------+
              |
              v
         HDMI Video Output
```

---

## Screen and TTY Handling

CamViewer runs directly on `tty1` without a desktop environment.

To avoid boot messages and cloud-init output being visible during camera
switching, a dedicated systemd unit is used:

- `clear-tty1.service`

This service:
- runs once after boot
- clears `tty1`
- ensures a clean framebuffer for fullscreen `ffplay`

It is intentionally separate from the player logic to keep responsibilities
clear and avoid race conditions during startup.

## Repository Layout

```
camviewer/
├── bin/
│   └── ipcams-cec-daemon.py
├── scripts/
│   └── cam-switcher.py
├── systemd/
│   ├── cam-switcher.service
│   ├── ipcams-cec-daemon.service
│   └── clear-tty1.service
├── env/
│   └── rtsp.env.example
├── .gitignore
└── README.md
```

---

## Remote Control Mapping

Observed on a Samsung TV remote (other TVs may differ):
- Fast Forward (CEC 0x49): next camera
- Rewind (CEC 0x48): previous camera

Key codes verified using `cec-ctl --monitor`.

---

## HDMI-CEC Behavior (Important)

To avoid stealing HDMI focus from other active inputs:
- `IMAGE_VIEW_ON` (0x04) and `ACTIVE_SOURCE` (0x82) are sent once only
  at daemon startup
- This allows the TV to learn the device name ("Cams")
- After that, only polite identification keepalive messages are sent
- The TV will not be forced to switch inputs repeatedly

This behavior is intentional and required for Samsung TVs.

---

## Configuration

RTSP configuration is provided via an environment file.

Copy and edit:

```bash
cp env/rtsp.env.example env/rtsp.env
```

Example content:

```bash
RTSP_USER=admin
RTSP_PASS=CHANGE_ME
RTSP_DOMAIN=lan
RTSP_PORT=554
RTSP_PATH=/h264Preview_01_sub
```

**Do not commit `rtsp.env`.**

---

## systemd Services

- **ipcams-cec-daemon.service**  
  Registers the HDMI-CEC playback device and listens for TV remote keys.

- **cam-switcher.service**  
  Runs ffplay on tty1 and switches between RTSP streams.

- **clear-tty1.service**  
  Clears boot messages from tty1 for kiosk operation.

---

## Installation (Manual Outline)

Paths may be adjusted to your environment.

```bash
sudo cp scripts/cam-switcher.py /home/ronzo/scripts/
sudo cp env/rtsp.env.example /home/ronzo/scripts/rtsp.env
sudo nano /home/ronzo/scripts/rtsp.env

sudo cp bin/ipcams-cec-daemon.py /usr/local/bin/
sudo chmod +x /usr/local/bin/ipcams-cec-daemon.py

sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now ipcams-cec-daemon.service
sudo systemctl enable --now cam-switcher.service
sudo systemctl enable --now clear-tty1.service
```

---

## Requirements

- Raspberry Pi with HDMI-CEC capable port
- Raspberry Pi OS (Bookworm or newer)
- ffmpeg / ffplay
- cec-utils (cec-ctl)
- TV with HDMI-CEC enabled (Samsung: AnyNet+)

---

## Screen and TTY Handling

CamViewer runs directly on `tty1` without a desktop environment.

To avoid boot messages and cloud-init output being visible during camera
switching, a dedicated systemd unit is used:

- `clear-tty1.service`

This service:
- runs once after boot
- clears `tty1`
- ensures a clean framebuffer for fullscreen `ffplay`

It is intentionally separate from the player logic to keep responsibilities
clear and avoid race conditions during startup.

---


## Status

Stable, in daily use, HDMI-CEC tested, fully reproducible.

---

## Author

elronzo
