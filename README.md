# IP Cams Viewer (Raspberry Pi + ffplay + HDMI-CEC)

This repository contains:
- `scripts/cam-switcher.py`: fullscreen ffplay-based RTSP viewer with camera switching
- `bin/ipcams-cec-daemon.py`: HDMI-CEC key listener (TV remote) that triggers switching via Unix socket
- `systemd/*.service`: unit files for running both components and optional tty clearing
- `env/rtsp.env.example`: example environment file (copy to `rtsp.env` locally; do not commit secrets)

## Keys
- Rewind: previous camera
- Fast Forward: next camera

## Install (manual outline)
- Copy scripts to `/home/ronzo/scripts/`
- Copy daemon to `/usr/local/bin/`
- Copy unit files to `/etc/systemd/system/`
- Create `/home/ronzo/scripts/rtsp.env` from `env/rtsp.env.example`
- `systemctl daemon-reload && systemctl enable --now ipcams-cec-daemon cam-switcher`
