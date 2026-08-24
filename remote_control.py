#!/usr/bin/env python3
import os
import sys
import signal
import socket

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


def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    cmd = sys.argv[1]
    command_map = {
        "--toggle": "toggle",
        "--start": "start",
        "--stop": "stop",
    }
    command = command_map.get(cmd)
    if not command:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    if IS_MACOS:
        if send_via_socket(command):
            sys.exit(0)
        print("MySuperWhisper is not running.")
        sys.exit(1)

    pid = get_running_pid()
    if not pid:
        print("MySuperWhisper is not running.")
        sys.exit(1)

    # SIGRTMIN doesn't exist on macOS; SIGINFO is the fallback used there
    # (must match mysuperwhisper.main.STOP_SIGNAL).
    stop_signal = getattr(signal, "SIGRTMIN", None) or signal.SIGINFO

    # SIGUSR1=toggle, SIGUSR2=start, stop_signal=stop
    sig_map = {
        "toggle": signal.SIGUSR1,
        "start": signal.SIGUSR2,
        "stop": stop_signal,
    }

    try:
        os.kill(pid, sig_map[command])
    except ProcessLookupError:
        print("Process not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
