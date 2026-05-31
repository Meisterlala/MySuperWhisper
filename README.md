# MySuperWhisper Fork

This repository is a fork of [OlivierMary/MySuperWhisper](https://github.com/OlivierMary/MySuperWhisper).

## Main Changes In This Fork

- Replaces the original transcription backend with IBM Granite Speech, using [`ibm-granite/granite-speech-4.1-2b`](https://huggingface.co/ibm-granite/granite-speech-4.1-2b) for final transcription and [`ibm-granite/granite-speech-4.1-2b-nar`](https://huggingface.co/ibm-granite/granite-speech-4.1-2b-nar) for live preview
- Adds live preview while recording with the Granite NAR preview model
- Adds chunked preemptive decoding with silence-aware chunk commits
- Adds model unload on inactivity
- Adds `remote_control.py` for external control, for example from Hyprland key press/release bindings:

```bash
python remote_control.py --toggle
python remote_control.py --start
python remote_control.py --stop
```
