#!/usr/bin/env python3
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from queue import Queue, Empty
from typing import Optional

# -----------------------
# Cameras (no cameras.txt)
# -----------------------
CAM_IDS = ["front", "garden", "livingroom", "cellar"]

# -----------------------
# RTSP settings from env
# (loaded via systemd EnvironmentFile=/home/ronzo/scripts/rtsp.env)
# -----------------------
RTSP_USER = os.environ.get("RTSP_USER")
RTSP_PASS = os.environ.get("RTSP_PASS")
RTSP_DOMAIN = os.environ.get("RTSP_DOMAIN", "lan")
RTSP_PORT = os.environ.get("RTSP_PORT", "554")
RTSP_PATH = os.environ.get("RTSP_PATH", "/h264Preview_01_sub")

# Just for on-screen header
CEC_OSD_BASE = os.environ.get("CEC_OSD_BASE", "IP Cams")

if not RTSP_USER or not RTSP_PASS:
    print("ERROR: RTSP_USER/RTSP_PASS not set (use EnvironmentFile=/home/ronzo/scripts/rtsp.env)", file=sys.stderr)
    sys.exit(1)

FFPLAY = "/usr/bin/ffplay"

# Matches your working command:
# ffplay -fs -fflags nobuffer -flags low_delay -rtsp_transport tcp -probesize 32 -analyzeduration 0 -nostats -loglevel error -an "$URL"
FFPLAY_ARGS_COMMON = [
    "-fs",
    "-fflags", "nobuffer",
    "-flags", "low_delay",
    "-rtsp_transport", "tcp",
    "-probesize", "32",
    "-analyzeduration", "0",
    "-nostats",
    "-loglevel", "error",
    "-an",
]

# ------------------------------------------------------------
# Control socket: created by this program and written to by the
# CEC daemon. We place it under XDG_RUNTIME_DIR (user-writable).
# cam-switcher.service should set XDG_RUNTIME_DIR=/run/user/<uid>.
# CEC daemon should use CAM_SWITCH_SOCK to point here.
# ------------------------------------------------------------
RUNDIR = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
SWITCH_SOCK = os.environ.get("CAM_SWITCH_SOCK") or os.path.join(RUNDIR, "ipcams", "cam-switch.sock")

ENV = os.environ.copy()
ENV["TERM"] = "linux"


def rtsp_url(cam_id: str) -> str:
    host = f"{cam_id}.{RTSP_DOMAIN}"
    return f"rtsp://{RTSP_USER}:{RTSP_PASS}@{host}:{RTSP_PORT}{RTSP_PATH}"


CAMS = [(cid, rtsp_url(cid)) for cid in CAM_IDS]

def clear_tty():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def banner(text: str):
    clear_tty()
    sys.stdout.write(text + "\n")
    sys.stdout.flush()

def kill_pgroup(p: Optional[subprocess.Popen], grace: float = 0.8):
    if not p or p.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        t0 = time.time()
        while time.time() - t0 < grace:
            if p.poll() is not None:
                return
            time.sleep(0.05)
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass


def start_ffplay(url: str) -> subprocess.Popen:
    cmd = [FFPLAY] + FFPLAY_ARGS_COMMON + [url]
    return subprocess.Popen(
        cmd,
        env=ENV,
        stdin=subprocess.DEVNULL,
        stdout=sys.stdout,
        stderr=sys.stderr,
        preexec_fn=os.setsid,
    )


def render_help(current: str, idx: int, total: int) -> str:
    return (
        f"{CEC_OSD_BASE} — {current} ({idx+1}/{total})\n"
        "CEC remote: Rew=prev, FF=next | Keyboard fallback: n/→/Space=next, p/←=prev, 1-4 direct, q quit\n"
        "\n"
    )


def set_tty_raw():
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    return old


def restore_tty(old):
    import termios
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key_nonblocking():
    import select
    r, _, _ = select.select([sys.stdin], [], [], 0.05)
    if not r:
        return None
    ch = sys.stdin.read(1)
    return ch if ch else None


def switch_socket_listener(q: Queue):
    # Ensure we can create the socket path
    os.makedirs(os.path.dirname(SWITCH_SOCK), exist_ok=True)

    # Create socket and listen for "next"/"prev"
    if os.path.exists(SWITCH_SOCK):
        os.unlink(SWITCH_SOCK)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(SWITCH_SOCK)
    os.chmod(SWITCH_SOCK, 0o666)
    s.listen(5)

    while True:
        conn, _ = s.accept()
        with conn:
            data = conn.recv(64).decode("utf-8", errors="ignore").strip()
            if data in ("next", "prev"):
                q.put(data)


def main():
    idx = 0
    ff: Optional[subprocess.Popen] = None

    q: Queue = Queue()
    threading.Thread(target=switch_socket_listener, args=(q,), daemon=True).start()

    def do_switch(to_idx: int):
        nonlocal idx, ff
        idx = to_idx % len(CAMS)
        name, url = CAMS[idx]

        banner(render_help(name, idx, len(CAMS)))

        kill_pgroup(ff)
        time.sleep(0.15)
        ff = start_ffplay(url)

    old_tty = set_tty_raw()
    try:
        do_switch(0)

        while True:
            # If ffplay died, restart current cam
            if ff and ff.poll() is not None:
                banner(render_help(CAMS[idx][0] + " (restarting)", idx, len(CAMS)))
                time.sleep(0.5)
                do_switch(idx)

            # CEC commands from daemon
            try:
                cmd = q.get_nowait()
                if cmd == "next":
                    do_switch(idx + 1)
                elif cmd == "prev":
                    do_switch(idx - 1)
            except Empty:
                pass

            # Keyboard fallback
            k = read_key_nonblocking()
            if not k:
                continue

            # Arrow escape sequences
            if k == "\x1b":
                k2 = read_key_nonblocking()
                if k2 == "[":
                    k3 = read_key_nonblocking()
                    if k3 == "C":  # Right
                        do_switch(idx + 1)
                    elif k3 == "D":  # Left
                        do_switch(idx - 1)
                continue

            k = k.lower()
            if k in ("n", " "):
                do_switch(idx + 1)
            elif k == "p":
                do_switch(idx - 1)
            elif k in ("1", "2", "3", "4"):
                do_switch(int(k) - 1)
            elif k == "q":
                break
    finally:
        restore_tty(old_tty)
        kill_pgroup(ff)
        try:
            if os.path.exists(SWITCH_SOCK):
                os.unlink(SWITCH_SOCK)
        except Exception:
            pass


if __name__ == "__main__":
    main()

