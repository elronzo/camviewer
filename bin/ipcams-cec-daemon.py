#!/usr/bin/env python3
import os
import re
import socket
import subprocess
import threading
import time

FORCE_ACTIVE_ONCE = os.environ.get("CEC_FORCE_ACTIVE_ONCE", "1") == "1"
_active_once_done = False

DEV = os.environ.get("CEC_DEV", "/dev/cec0")
OSD_BASE = os.environ.get("CEC_OSD_BASE", "Cams")

KEEPALIVE_SEC = int(os.environ.get("CEC_KEEPALIVE_SEC", "120"))

# Command socket for manual control of this daemon (optional)
RUNDIR = os.environ.get("RUNTIME_DIR", "/run/ipcams")
DAEMON_SOCK = os.path.join(RUNDIR, "ipcams-cec.sock")

# Socket to cam-switcher (must match cam-switcher service)
SWITCH_SOCK = os.environ.get("CAM_SWITCH_SOCK", "/run/user/1000/ipcams/cam-switch.sock")

FF_KEY = 0x49  # Fast Forward -> next
RW_KEY = 0x48  # Rewind -> prev


def run(cmd, timeout=5):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    return p.returncode, p.stdout


def get_phys_addr():
    rc, out = run(["/usr/bin/cec-ctl", "-d", DEV, "-x"], timeout=5)
    m = re.search(r"Physical Address\s*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", out)
    return m.group(1) if m else "1.0.0.0"


def phys_to_payload(pa: str) -> str:
    a, b, c, d = [int(x) for x in pa.split(".")]
    b1 = (a << 4) | b
    b2 = (c << 4) | d
    return f"0x{b1:02x}:0x{b2:02x}"

def announce(osd_name: str):
    global _active_once_done

    if not os.path.exists(DEV):
        return

    pa = get_phys_addr()
    payload = phys_to_payload(pa)

    # Always: claim playback + set OSD name (polite)
    run(["/usr/bin/cec-ctl", "-d", DEV, "--playback", "--osd-name", osd_name, "-L"], timeout=5)

    # Once: do a full "I'm a source" handshake so Samsung learns our name
    if FORCE_ACTIVE_ONCE and not _active_once_done:
        # One Touch Play (may switch once)
        run(["/usr/bin/cec-ctl", "-d", DEV, "--playback", "--osd-name", osd_name,
             "-t", "0", "--custom-command", "cmd=0x04"], timeout=5)

        # Active Source (may switch once)
        run(["/usr/bin/cec-ctl", "-d", DEV, "--playback", "--osd-name", osd_name,
             "-t", "15", "--custom-command", f"cmd=0x82,payload={payload}"], timeout=5)

        _active_once_done = True


def send_switch(cmd: str):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(SWITCH_SOCK)
        s.sendall(cmd.encode("utf-8"))
        s.close()
    except Exception:
        pass


def monitor_cec_keys():
    p = subprocess.Popen(
        ["/usr/bin/cec-ctl", "-d", DEV, "--monitor-all", "--show-raw", "--verbose"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    pending_ucp = False

    for line in p.stdout or []:
        line = line.strip()

        if "USER_CONTROL_PRESSED" in line:
            pending_ucp = True
            continue

        if pending_ucp and line.startswith("Raw:"):
            m = re.search(r"\b0x44\b\s+0x([0-9a-fA-F]{2})\b", line)
            pending_ucp = False
            if not m:
                continue
            key = int(m.group(1), 16)

            if key == FF_KEY:
                send_switch("next")
            elif key == RW_KEY:
                send_switch("prev")
            continue

        if pending_ucp and ("USER_CONTROL_RELEASED" in line or line.startswith("Received")):
            pending_ucp = False


def keepalive_loop():
    while True:
        announce(OSD_BASE)
        time.sleep(KEEPALIVE_SEC)


def socket_server():
    os.makedirs(RUNDIR, exist_ok=True)
    if os.path.exists(DAEMON_SOCK):
        os.unlink(DAEMON_SOCK)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(DAEMON_SOCK)
    os.chmod(DAEMON_SOCK, 0o666)
    s.listen(5)

    current_name = OSD_BASE

    while True:
        conn, _ = s.accept()
        with conn:
            data = conn.recv(4096).decode("utf-8", errors="ignore").strip()
            if not data:
                continue

            if data == "quit":
                conn.sendall(b"ok\n")
                return

            if data == "announce":
                announce(current_name)
                conn.sendall(b"ok\n")
                continue

            if data.startswith("name "):
                current_name = data[5:].strip() or OSD_BASE
                announce(current_name)
                conn.sendall(b"ok\n")
                continue

            conn.sendall(b"unknown\n")


def main():
    for _ in range(30):
        if os.path.exists(DEV):
            break
        time.sleep(1)

    threading.Thread(target=keepalive_loop, daemon=True).start()
    threading.Thread(target=monitor_cec_keys, daemon=True).start()
    socket_server()


if __name__ == "__main__":
    main()

