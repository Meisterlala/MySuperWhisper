# MySuperWhisper Fork

This repository is a fork of [OlivierMary/MySuperWhisper](https://github.com/OlivierMary/MySuperWhisper).

## Main Changes In This Fork

- Replaces the original transcription backend with IBM Granite Speech, using [`ibm-granite/granite-speech-4.1-2b`](https://huggingface.co/ibm-granite/granite-speech-4.1-2b) for final transcription and [`ibm-granite/granite-speech-4.1-2b-nar`](https://huggingface.co/ibm-granite/granite-speech-4.1-2b-nar) for live preview
- Adds live preview while recording with the Granite NAR preview model
- Adds chunked preemptive decoding with silence-aware chunk commits
- Adds model unload on inactivity and unload on demand from the tray menu
- Adds `remote_control.py` for external control, for example from Hyprland key press/release bindings:

```bash
python remote_control.py --toggle
python remote_control.py --start
python remote_control.py --stop
```

Global keyboard shortcuts are disabled by default, so the application only reacts to
remote-control commands. They can be enabled at runtime from **Global keyboard shortcuts**
in the tray menu; the choice is persisted in `~/.config/mysuperwhisper/config.json`.

The Granite preview model uses Flash Attention when `flash-attn` is installed and falls
back to standard attention otherwise. CUDA is required for live preview; final Granite
transcription falls back to CPU when CUDA is unavailable.

## Installing on macOS

```bash
./install-mac.sh
```

Builds `MySuperWhisper.app`, installs it to `/Applications`, and registers a LaunchAgent
so it starts at login. Re-run it any time to rebuild and reinstall. Grant Accessibility
permission when prompted (System Settings opens automatically at the end).

- `./launch-mac.sh` — restart the app after quitting it
- `python remote_control.py --toggle` — start/stop recording remotely

## Installing on Linux

```bash
./install.sh
```
