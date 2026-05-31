# MySuperWhisper

<p align="center">
  <img src="mysuperwhisper.svg" alt="MySuperWhisper Logo" width="128">
</p>

<p align="center">
  <strong>Global Voice Dictation for Linux using IBM Granite Speech</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#voice-commands">Voice Commands</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#contributing">Contributing</a>
</p>

---

MySuperWhisper is a Linux desktop application that provides **global voice-to-text transcription** using IBM Granite Speech models. Press **Double Ctrl** anywhere on your system to start recording, speak, and press **Double Ctrl** again - your speech is transcribed and automatically typed into any application.

## Features

- 🎤 **Global Hotkey** - Fully configurable shortcuts work in any application
- 🚀 **GPU Acceleration** - Uses CUDA when available, with CPU fallback for final transcription
- 🧠 **Granite Speech Backend** - Final transcription uses `ibm-granite/granite-speech-4.1-2b`
- 👀 **Fast Live Preview** - Live preview uses `ibm-granite/granite-speech-4.1-2b-nar` when supported
- 🗣️ **Voice Commands** - Say "new line" or "enter" to control text formatting
- 📜 **History** - Triple Ctrl opens recent transcriptions for quick re-use
- 🔔 **Notifications** - Audio beeps and system notifications for feedback
- 🌍 **Multi-language** - Voice commands work in French, English, and Spanish
- 🖥️ **System Tray** - Easy access to settings and device selection

## Requirements

- Linux (X11 or Wayland)
- Python 3.8+
- NVIDIA GPU with CUDA recommended
- PulseAudio or PipeWire

## Installation

### Quick Install (Ubuntu/Debian)

```bash
# Clone the repository
git clone https://github.com/oliviermary/MySuperWhisper.git
cd MySuperWhisper

# Run the installer
chmod +x install.sh
./install.sh
```

### Manual Installation

```bash
# System dependencies (python3-tk is required for the history popup and shortcut config)
sudo apt install python3-venv python3-pip python3-tk xdotool libnotify-bin pulseaudio-utils

# For Wayland support (optional)
sudo apt install wtype

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional but recommended for Granite live preview on GPU
pip install flash-attn --no-build-isolation
```

### Install with pip (without cloning)

You can also install the package straight from GitHub into a virtualenv. You
still need the GUI/system dependency `python3-tk`:

```bash
# System dependency for the GUI (tkinter)
sudo apt install python3-tk

# Create a virtualenv and install the package into it
python3 -m venv MySuperWhisper
./MySuperWhisper/bin/pip install -U git+https://github.com/OlivierMary/MySuperWhisper.git

# Run the app
./MySuperWhisper/bin/mysuperwhisper
```

## Usage

### Starting the Application

```bash
# Using the virtual environment
./venv/bin/python -m mysuperwhisper

# Or with the legacy script
./venv/bin/python mysuperwhisper.py
```

### Keyboard Shortcuts

**Default shortcuts:**

| Shortcut | Action |
|----------|--------|
| **Double Left Ctrl** | Start/Stop recording |
| **Triple Left Ctrl** | Open transcription history |

Keyboard shortcuts are **fully configurable** via the system tray menu under "⌨️ Keyboard Shortcuts". Click "Configure..." to open the shortcut detection popup:

1. **Press your desired shortcut** exactly as you want to use it (e.g., double-tap Ctrl+A, triple Right Ctrl, single F1...)
2. The popup **shows in real-time** what is detected (key, combination, and tap count)
3. Click **OK** to validate

You can use **any key or combination**: modifier keys (Ctrl, Alt, Shift), function keys (F1-F12), regular keys (A-Z, 0-9), or combinations like Ctrl+A, Alt+Space, Shift+F1, etc.

### System Tray

Right-click the tray icon to access:
- Enable/disable notifications
- Toggle "Use clipboard to paste" (off by default — see [Paste behavior](#paste-behavior))
- Configure keyboard shortcuts
- View transcription history
- Test microphone with audio loopback
- Reload speech models
- Choose input/output audio devices
- Open configuration files

### Tray Icon Colors

| Color | Status |
|-------|--------|
| 🟡 Yellow | Loading model |
| 🟢 Green | Ready |
| 🔴 Red | Recording |
| 🟠 Orange | Transcribing |
| 🔵 Blue | Mic test mode |

## Voice Commands

MySuperWhisper recognizes voice commands in multiple languages:

### New Line Commands
| Language | Commands |
|----------|----------|
| English | "new line", "newline", "line break", "next line" |
| French | "retour à la ligne", "nouvelle ligne", "à la ligne" |
| Spanish | "nueva línea", "salto de línea", "línea siguiente" |

### Validation Commands (Press Enter)
| Language | Commands |
|----------|----------|
| English | "enter", "submit", "validate", "send", "confirm" |
| French | "valider", "entrée", "entrer" |
| Spanish | "enviar", "validar", "confirmar", "entrar" |

### Example

Say: *"Hello new line How are you enter"*

Result: Types "Hello", creates a new line, types "How are you", then presses Enter.

> **Note**: In standard applications, "new line" uses `Shift+Enter` (soft line break). In **terminal emulators**, it intelligently switches to `Ctrl+Shift+V` to paste the text with actual newlines, ensuring correct behavior.

### Paste behavior

There are two ways to insert the transcribed text, controlled by the
**"Use clipboard to paste"** tray option (and the `use_clipboard_to_paste`
config key):

| Mode | `use_clipboard_to_paste` | How it works | Trade-off |
|------|--------------------------|--------------|-----------|
| **Direct typing** (default) | `false` | Types the text directly (`xdotool type` / `wtype`) | Your clipboard **and its history stay untouched**. Slightly slower on long texts; some non-Latin scripts (e.g. CJK) may not type reliably depending on your keyboard layout. |
| **Clipboard paste** | `true` | Copies to the clipboard, then sends `Ctrl+V` / `Ctrl+Shift+V` | Fast and handles any Unicode reliably, but **overwrites the clipboard** (and adds an entry to clipboard-manager history). |

Direct typing is the default so dictation never clobbers what you had copied.
If you mostly dictate non-Latin scripts, enable clipboard paste.

## Configuration

Configuration is stored in `~/.config/mysuperwhisper/config.json`:

```json
{
    "transcription_model": "ibm-granite/granite-speech-4.1-2b",
    "preview_model": "ibm-granite/granite-speech-4.1-2b-nar",
    "language": "en",
    "record_hotkey": "ctrl_l+a",
    "record_press_count": 2,
    "history_hotkey": "ctrl_l",
    "history_press_count": 3,
    "input_device": "Your Microphone",
    "output_device": "Your Speakers",
    "system_notifications_enabled": true,
    "sound_notifications_enabled": true,
    "use_clipboard_to_paste": false
}
```

This example configures:
- Granite main and preview speech models
- Double press of Left Ctrl + A for recording
- Triple press of Left Ctrl for history
- English voice-command language

### Configuration Options

- **transcription_model** / **preview_model**: Granite model identifiers for final transcription and live preview
- **language**: Language used for voice-command processing
- **record_hotkey**: Key or combination for recording - any key (`"ctrl_l"`, `"f1"`, `"a"`) or combination (`"ctrl_l+a"`, `"alt+space"`)
- **record_press_count**: Number of presses for recording - `1` (single), `2` (double), or `3` (triple)
- **history_hotkey**: Key or combination for opening history popup
- **history_press_count**: Number of presses for history popup
- **input_device** / **output_device**: Audio device names (set via tray menu)
- **system_notifications_enabled**: Show desktop notifications
- **sound_notifications_enabled**: Play audio beeps
- **use_clipboard_to_paste**: How transcribed text is inserted (see [Paste behavior](#paste-behavior)). `false` (default) types the text directly and leaves your clipboard untouched; `true` pastes through the system clipboard

**Tip:** You can configure keyboard shortcuts easily through the system tray menu under "⌨️ Keyboard Shortcuts".

### Model Behavior

| Component | Model | Notes |
|-----------|-------|-------|
| Final transcription | `ibm-granite/granite-speech-4.1-2b` | Main ASR model used for pasted text |
| Live preview | `ibm-granite/granite-speech-4.1-2b-nar` | Optional fast preview model; requires CUDA and `flash-attn` |

## File Locations

| File | Location |
|------|----------|
| Configuration | `~/.config/mysuperwhisper/config.json` |
| Logs | `~/.local/share/mysuperwhisper/logs/` |
| History | `~/.local/share/mysuperwhisper/history.json` |

## Project Structure

```
MySuperWhisper/
├── mysuperwhisper/          # Main package
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── main.py              # Application logic
│   ├── config.py            # Configuration management
│   ├── audio.py             # Audio capture
│   ├── transcription.py     # Granite Speech integration
│   ├── voice_commands.py    # Voice command processing
│   ├── paste.py             # Text input simulation
│   ├── notifications.py     # Notifications
│   ├── keyboard.py          # Hotkey handling
│   ├── history.py           # History management
│   └── tray.py              # System tray
├── install.sh               # Installation script
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
├── CONTRIBUTING.md          # Contribution guidelines
└── README.md                # This file
```

## Troubleshooting

### No audio input
- Check microphone permissions
- Verify correct input device in tray menu
- Use "Mic Test" to verify audio is being captured

### Slow transcription
- Ensure CUDA is available for GPU acceleration
- Check if running in CPU mode (indicated in tray tooltip with [CPU])
- Live preview is disabled automatically when the preview model requirements are unavailable

### GPU issues after driver update
- If you recently updated your NVIDIA drivers, the app might fallback to CPU mode or fail to load the model.
- **Solution:** Restart your computer to ensure the new drivers are correctly loaded.

### Text not typed in some applications
- Some applications may not accept simulated keyboard input
- **Workaround:** The transcribed text is **always copied to your clipboard**. If automated typing fails, you can simply paste it manually (Ctrl+V).

### New line doesn't work in terminal
- This should be handled automatically now (auto-switch to Ctrl+Shift+V)
- If not, try pasting manually using Ctrl+Shift+V

## Dependencies

MySuperWhisper uses these excellent open-source projects:

| Package | Purpose | License |
|---------|---------|---------|
| [transformers](https://github.com/huggingface/transformers) | Granite Speech model runtime | Apache-2.0 |
| [torch](https://pytorch.org/) | Model execution | BSD-style |
| [pynput](https://github.com/moses-palmer/pynput) | Keyboard monitoring | LGPL-3.0 |
| [pystray](https://github.com/moses-palmer/pystray) | System tray | LGPL-3.0 |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | Audio capture | MIT |
| [numpy](https://numpy.org/) | Numerical processing | BSD |
| [Pillow](https://pillow.readthedocs.io/) | Image processing | HPND |
| [pyperclip](https://github.com/asweigart/pyperclip) | Clipboard access | BSD |

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- IBM for the Granite Speech models
- Hugging Face for the Transformers runtime
- All contributors and users of this project

---

<p align="center">
  Made with ❤️ for the Linux community
</p>
