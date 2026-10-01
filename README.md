# MySuperWhisper Fork

This repository is a fork of [OlivierMary/MySuperWhisper](https://github.com/OlivierMary/MySuperWhisper).

## Main Changes In This Fork

- Uses [`ibm-granite/granite-speech-5.0-470m-turboctc-nc`](https://huggingface.co/ibm-granite/granite-speech-5.0-470m-turboctc-nc) for English transcription and live preview
- Adds chunked preemptive decoding with silence-aware chunk commits
- Adds model unload on inactivity and unload on demand from the tray menu
- Adds macOS support alongside Linux (CoreAudio input, AppleScript notifications,
  Cmd+V pasting, MPS acceleration and a packaged `.app` bundle)
- Adds `remote_control.py` for external control, for example from Hyprland key press/release bindings:

```bash
python remote_control.py --toggle
python remote_control.py --start
python remote_control.py --stop
```

Global keyboard shortcuts are disabled by default, so the application only reacts to
remote-control commands. They can be enabled at runtime from **Global keyboard shortcuts**
in the tray menu; the choice is persisted in `~/.config/mysuperwhisper/config.json`.

Live preview reuses the same Granite Speech 5.0 model as final transcription. Final
transcription falls back to CPU when no GPU is available.

Enable **Live typing** in the tray menu to type words as you speak and correct
them as the transcription updates. Keep the cursor in the same input while recording.

## Installation

### Linux

```bash
./install.sh
```

Creates `venv/`, installs the system and Python dependencies, and sets up the desktop
entry. Remote control uses POSIX signals (`SIGUSR1`/`SIGUSR2`/`SIGRTMIN`).

### macOS

```bash
./install-mac.sh
```

Builds `MySuperWhisper.app`, installs it to `/Applications`, and registers a LaunchAgent
so it starts at login. Re-run it any time to rebuild and reinstall. Grant Accessibility
permission when prompted (System Settings opens automatically at the end).

- `./launch-mac.sh` — restart the app after quitting it

Remote control on macOS goes over a Unix socket at `/tmp/mysuperwhisper.sock` instead of
signals: pystray parks the main thread inside AppKit's run loop, so a Python signal
handler would never run.
