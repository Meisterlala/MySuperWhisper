#!/usr/bin/env python3
import os
import sys
import signal
import socket
import time

REMOTE_SOCKET_PATH = "/tmp/mysuperwhisper.sock"

IS_MACOS = sys.platform == "darwin"

if not IS_MACOS:
    import fcntl


def get_running_pid():
    lock_file = "/tmp/mysuperwhisper.lock"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r+') as f:
                try:
                    fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return None
                except OSError:
                    pass
                content = f.read().strip()
                if content:
                    return int(content)
        except (OSError, ValueError):
            pass
    return None


def send_via_socket(command):
    """
    Send a command over the Unix socket used on macOS.

    Needed because pystray blocks the main thread inside AppKit's run loop
    there, so the app never gets a chance to process a POSIX signal (must
    match mysuperwhisper.main._start_remote_control_socket).
    """
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect(REMOTE_SOCKET_PATH)
        client.sendall(command.encode("utf-8"))
        client.close()
        return True
    except OSError:
        return False


def _held_key_devices():
    """Find the held non-modifier key on physical input devices."""
    from evdev import InputDevice, ecodes, list_devices

    modifiers = {
        ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
        ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
        ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
        ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA,
    }
    candidates = []
    for path in list_devices():
        try:
            device = InputDevice(path)
            if not device.phys or ecodes.EV_KEY not in device.capabilities():
                device.close()
                continue
            pressed = set(device.active_keys()) - modifiers
            if pressed:
                candidates.append((device, pressed))
            else:
                device.close()
        except OSError:
            continue
    keys = set().union(*(pressed for _, pressed in candidates))
    if len(keys) != 1:
        for device, _ in candidates:
            device.close()
        raise RuntimeError("Cannot identify one held physical shortcut key")
    key_code = keys.pop()
    return key_code, [device for device, pressed in candidates if key_code in pressed]


def wait_for_key_release():
    """Poll the hardware key state; virtual typing cannot consume this release."""
    key_code, devices = _held_key_devices()
    try:
        while any(key_code in device.active_keys() for device in devices):
            time.sleep(0.02)
        return True
    finally:
        for device in devices:
            device.close()


def send_command(command):
    """Send an existing remote-control command to the running instance."""
    if IS_MACOS:
        return send_via_socket(command)
    pid = get_running_pid()
    if not pid:
        return False
    stop_signal = getattr(signal, "SIGRTMIN", None) or signal.SIGINFO
    sig_map = {"toggle": signal.SIGUSR1, "start": signal.SIGUSR2, "stop": stop_signal}
    os.kill(pid, sig_map[command])
    return True


def hold_key():
    """Start on press and stop when the held physical key is released."""
    if not send_command("start"):
        raise RuntimeError("MySuperWhisper is not running")
    try:
        wait_for_key_release()
    finally:
        send_command("stop")


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "--hold" and not IS_MACOS:
        try:
            hold_key()
        except (OSError, RuntimeError, ImportError) as exc:
            print(f"Hold shortcut failed: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    command_map = {
        "--toggle": "toggle",
        "--start": "start",
        "--stop": "stop",
    }
    command = command_map.get(cmd)
    if not command:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    try:
        if not send_command(command):
            print("MySuperWhisper is not running.")
            sys.exit(1)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
