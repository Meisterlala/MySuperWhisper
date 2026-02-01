"""
Configuration management for MySuperWhisper.
Handles loading/saving settings and XDG directory setup.
"""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

# --- XDG Standard Directories ---
CONFIG_DIR = Path.home() / ".config" / "mysuperwhisper"
DATA_DIR = Path.home() / ".local" / "share" / "mysuperwhisper"
LOG_DIR = DATA_DIR / "logs"
HISTORY_FILE = DATA_DIR / "history.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Create directories if they don't exist
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- Logging Configuration ---
LOG_FILE = LOG_DIR / "mysuperwhisper.log"

# Main logger
logger = logging.getLogger("MySuperWhisper")
logger.setLevel(logging.DEBUG)

# Log format
log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# File handler (rotation: 5 files of 1MB max)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_format)
logger.addHandler(file_handler)

# Note: Rotation happens automatically when file reaches 1MB (maxBytes)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_format)
logger.addHandler(console_handler)


def log(message, level="info"):
    """Log a message with the specified level."""
    if level == "debug":
        logger.debug(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:
        logger.info(message)


class Config:
    """Application configuration singleton."""

    def __init__(self):
        # Default values
        self.model_size = "medium"
        self.language = "en"  # Default to English
        self.system_notifications_enabled = True
        self.sound_notifications_enabled = True
        self.live_preview_enabled = True
        self.input_device = None
        self.output_device = None

    def load(self):
        """Load configuration from file."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)

                self.model_size = data.get("model_size", "medium")
                self.language = data.get("language", "en")
                self.system_notifications_enabled = data.get("system_notifications_enabled", True)
                self.sound_notifications_enabled = data.get("sound_notifications_enabled", True)
                self.live_preview_enabled = data.get("live_preview_enabled", True)
                self.input_device = data.get("input_device")
                self.output_device = data.get("output_device")

                log(f"Configuration loaded from {CONFIG_FILE}")
        except Exception as e:
            log(f"Error loading config: {e}", "error")

    def save(self):
        """Save configuration to file."""
        try:
            data = {
                "model_size": self.model_size,
                "language": self.language,
                "system_notifications_enabled": self.system_notifications_enabled,
                "sound_notifications_enabled": self.sound_notifications_enabled,
                "live_preview_enabled": self.live_preview_enabled,
                "input_device": self.input_device,
                "output_device": self.output_device
            }

            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)

            log("Configuration saved.")
        except Exception as e:
            log(f"Error saving config: {e}", "error")

    def restore_audio_devices(self):
        """
        Restore audio devices from config.
        Now handled automatically by audio.start_stream() using config.
        """
        pass


# Global config instance
config = Config()
