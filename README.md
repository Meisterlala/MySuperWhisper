# MySuperWhisper

<p align="center">
  <img src="mysuperwhisper.svg" alt="MySuperWhisper Logo" width="128">
</p>

<p align="center">
  <strong>Global Voice Dictation for Linux using Whisper AI</strong>
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

MySuperWhisper is a Linux desktop application that provides **global voice-to-text transcription** using OpenAI's Whisper model. Simply press **Double Ctrl** anywhere on your system to start recording, speak, and press **Double Ctrl** again - your speech is transcribed and automatically typed into any application.

## Features

- 🎤 **Global Hotkey** - Double Ctrl works in any application
- 🚀 **GPU Acceleration** - Uses CUDA with INT8 quantization for fast transcription
- 🧠 **Multiple Models** - Choose from tiny to large-v3 based on your needs
- 🗣️ **Voice Commands** - Say "new line" or "enter" to control text formatting
- 📜 **History** - Triple Ctrl opens recent transcriptions for quick re-use
- 🔔 **Notifications** - Audio beeps and system notifications for feedback
- 🌍 **Multi-language** - Voice commands work in French, English, and Spanish
- 🖥️ **System Tray** - Easy access to settings and device selection

## Requirements

- Linux (X11 or Wayland)
- Python 3.8+
- NVIDIA GPU with CUDA (optional, falls back to CPU)
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
# System dependencies
sudo apt install python3-venv python3-pip xdotool libnotify-bin pulseaudio-utils

# For Wayland support (optional)
sudo apt install wtype

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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

| Shortcut | Action |
|----------|--------|
| **Double Ctrl** | Start/Stop recording |
| **Triple Ctrl** | Open transcription history |

### System Tray

Right-click the tray icon to access:
- Enable/disable notifications
- View transcription history
- Test microphone with audio loopback
- Select AI model size
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

Result: Types "Hello", presses Shift+Enter for new line, types "How are you", then presses Enter.

> **Note**: New line commands use Shift+Enter, which creates a soft line break. This works in most applications but may not work in terminal emulators.

## Configuration

Configuration is stored in `~/.config/mysuperwhisper/config.json`:

```json
{
    "model_size": "medium",
    "input_device_name": "Your Microphone",
    "output_device_name": "Your Speakers",
    "system_notifications_enabled": true,
    "sound_notifications_enabled": true
}
```

### Model Sizes

| Model | VRAM | Speed | Accuracy |
|-------|------|-------|----------|
| tiny | ~1GB | Fastest | Basic |
| base | ~1GB | Fast | Good |
| small | ~2GB | Medium | Better |
| **medium** | ~2GB | Standard | **Recommended** |
| large-v3 | ~3.3GB | Slow | Best |

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
│   ├── transcription.py     # Whisper integration
│   ├── voice_commands.py    # Voice command processing
│   ├── paste.py             # Text input simulation
│   ├── notifications.py     # Notifications
│   ├── keyboard.py          # Hotkey handling
│   ├── history.py           # History management
│   └── tray.py              # System tray
├── mysuperwhisper.py        # Legacy single-file version
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
- Try a smaller model (tiny, base, small)
- Check if running in CPU mode (indicated in tray tooltip with [CPU])

### Text not typed in some applications
- Some applications may not accept simulated keyboard input
- Try using Ctrl+V to paste from clipboard (text is always copied there)

### New line doesn't work in terminal
- This is a known limitation of terminal emulators
- Shift+Return is used for new lines, which terminals interpret differently

## Dependencies

MySuperWhisper uses these excellent open-source projects:

| Package | Purpose | License |
|---------|---------|---------|
| [faster-whisper](https://github.com/guillaumekln/faster-whisper) | Whisper implementation | MIT |
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

- OpenAI for the Whisper model
- The faster-whisper team for the optimized implementation
- All contributors and users of this project

---

<p align="center">
  Made with ❤️ for the Linux community
</p>
