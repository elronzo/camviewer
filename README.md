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

## Hardware Platform and Performance Considerations

The reference system for CamViewer is a **Raspberry Pi Zero 2 W**.

This works reliably **when using camera sub-streams** (low resolution / low bitrate),
which is the recommended mode for kiosk-style, always-on monitoring.

### Tested Reference Setup

- **Raspberry Pi Zero 2 W**
- HDMI output at 1080p
- RTSP **sub-stream** (typically 640×360 or 720×576, H.264)
- `ffplay` with low-latency flags
- Single camera displayed at a time

Under these conditions, CPU load remains low and playback is stable.

---

## Raspberry Pi Hardware Recommendations

CamViewer itself is lightweight; performance is dominated by **RTSP decode**.
The following guidance applies:

### Recommended by Stream Type

| Stream Type | Recommended Hardware |
|------------|---------------------|
| Sub-stream (≤ 720p, low bitrate) | Raspberry Pi Zero 2 W |
| 1080p main stream (single camera) | Raspberry Pi 3B+ or Pi 4 |
| 4K or high-bitrate 1080p | Raspberry Pi 4 (2 GB+ RAM) |
| Multiple cameras / future grid view | Raspberry Pi 4 or Pi 5 |

### Notes

- H.264 is strongly recommended; H.265 decoding support varies by model and OS.
- Hardware decoding is handled by the VideoCore GPU; CPU usage scales mostly with bitrate.
- Using camera sub-streams dramatically reduces latency, heat and power usage.
- Only **one stream is decoded at a time** in the current design.

---

## General Recommendation

For a **simple, reliable, low-power camera viewer**, a Raspberry Pi Zero 2 W is sufficient
and preferred.

If you intend to:
- use main streams instead of sub-streams
- increase resolution or bitrate
- experiment with multi-camera layouts

then a Raspberry Pi 4 or newer is recommended.

The software design does not depend on a specific Raspberry Pi model.

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
