#!/usr/bin/env python3
import os
import sys
import signal
from pathlib import Path

def get_running_pid():
    lock_file = "/tmp/mysuperwhisper.lock"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                content = f.read().strip()
                if content:
                    return int(content)
        except:
            pass
    return None

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    cmd = sys.argv[1]
    pid = get_running_pid()
    
    if not pid:
        print("MySuperWhisper is not running.")
        sys.exit(1)

    # SIGUSR1=toggle, SIGUSR2=start, SIGRTMIN=stop
    sig_map = {
        "--toggle": signal.SIGUSR1,
        "--start": signal.SIGUSR2,
        "--stop": signal.SIGRTMIN
    }

    sig = sig_map.get(cmd)
    if not sig:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        print("Process not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
