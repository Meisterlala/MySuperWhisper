#!/usr/bin/env python3
"""
MySuperWhisper - Global Voice Dictation Tool

A Linux desktop application that provides global voice-to-text transcription
using OpenAI's Whisper model. Press Double Ctrl to start/stop recording,
and the transcribed text is automatically typed into any application.

Features:
- Global hotkey (Double Ctrl) works in any application
- Supports multiple Whisper model sizes (tiny to large-v3)
- GPU acceleration with INT8 quantization
- Voice commands for newlines and validation
- Transcription history with Triple Ctrl
- System tray integration
- Multi-language support for voice commands (FR/EN/ES)

Usage:
    python -m mysuperwhisper
    python -m mysuperwhisper --playback  # Debug mode with audio playback

Author: Olivier Mary
License: MIT
"""

import sys

# Hack to access system PyGObject (gi) from venv for AppIndicator support
sys.path.append("/usr/lib/python3/dist-packages")

import argparse
import os
import queue
import signal
import sys
import threading
import time

from . import audio, history, keyboard, transcription, tray
from .config import CONFIG_DIR, LOG_FILE, config, log
from .notifications import play_sound, send_live_notification, send_notification
from .paste import paste_text, press_enter_key
from .voice_commands import process_voice_commands

# Processing queue
processing_queue = queue.Queue()

# Command line arguments
args = None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Global Voice Dictation Tool")
    parser.add_argument(
        "--playback",
        action="store_true",
        help="Enable audio playback after recording (debug)",
    )
    parser.add_argument(
        "--toggle",
        action="store_true",
        help="Toggle recording on a running instance and exit",
    )
    parser.add_argument(
        "--start",
        action="store_true",
        help="Start recording on a running instance (no-op if already recording)",
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop recording on a running instance (no-op if not recording)",
    )
    return parser.parse_args()


# Global state for sleep mode
_last_activity_time = time.time()
_is_sleeping = False
_is_model_loaded = True

# Inactivity timeouts (seconds)
AUTO_SLEEP_TIMEOUT = 15
MODEL_UNLOAD_TIMEOUT = 60 * 15


def update_activity():
    """Update last activity timestamp and wake up if sleeping."""
    global _last_activity_time, _is_sleeping, _is_model_loaded
    _last_activity_time = time.time()

    if _is_sleeping:
        log("Waking up from sleep mode...")
        _is_sleeping = False
        audio.start_stream()
        tray.update_tray("idle")

    if not _is_model_loaded:
        log("Waking up: Reloading model...")
        tray.update_tray("loading")
        transcription.load_model()
        _is_model_loaded = True
        tray.update_tray("idle")


def on_double_ctrl():
    """Handle Double Ctrl: toggle recording."""
    update_activity()
    if audio.is_currently_recording():
        stop_and_process()
    else:
        start_recording()


def on_triple_ctrl():
    """Handle Triple Ctrl: open history popup."""
    update_activity()
    if not history.is_popup_open():
        history.open_history_popup_async()


def start_recording():
    """Start voice recording."""
    global _is_recording, _live_preview_thread
    _is_recording = True

    audio.start_recording()

    # Do notifications in background
    def _notify():
        play_sound("start")
        tray.update_tray("recording")
        send_notification("MySuperWhisper", "Listening...", "audio-input-microphone")

    threading.Thread(target=_notify, daemon=True).start()

    # Start live preview loop
    _live_preview_thread = threading.Thread(target=live_preview_worker, daemon=True)
    _live_preview_thread.start()


def stop_and_process():
    """Stop recording and queue audio for processing."""
    global _is_recording
    _is_recording = False

    audio_data = audio.stop_recording()

    if audio_data is None:
        play_sound("error")
        tray.update_tray("idle")
        return

    # Check minimum duration (1 second at 48kHz)
    if len(audio_data) < 48000:
        log("Recording too short (< 1s), ignoring.", "warning")
        # No error sound for short recordings as requested
        tray.update_tray("idle")
        return

    # Immediate feedback sound
    play_sound("success")

    tray.update_tray("processing")
    processing_queue.put(audio_data)


def live_preview_worker():
    """Worker thread for live transcription preview."""
    log("Live preview worker started", "debug")
    last_preview_time = time.time()

    while _is_recording:
        time.sleep(0.01)
        if not config.live_preview_enabled:
            break

        now = time.time()

        # Update preview every 0.6 seconds if we have audio
        if now - last_preview_time >= 0.6:
            audio_data = audio.get_current_buffer()
            if audio_data is not None:
                audio_len = len(audio_data)
                if audio_len > 32000:  # Min ~0.7s of audio
                    try:
                        audio_16k = audio.prepare_for_whisper(audio_data)
                        # Use fast mode (beam_size=1) for live preview
                        text = transcription.transcribe(audio_16k, fast=True)
                        # log(f"Live preview text: '{text}'", "debug")
                        if text:
                            send_live_notification(text)
                    except Exception as e:
                        log(f"Live preview error: {e}", "debug")
            last_preview_time = now
    log("Live preview worker stopped", "debug")


def audio_processing_loop():
    """
    Main processing loop running in a separate thread.
    Handles transcription and text pasting.
    """
    while True:
        # Wait for audio data
        audio_data = processing_queue.get()

        # Optional debug playback
        if args and args.playback:
            log("Debug playback...", "debug")
            try:
                import sounddevice as sd

                sd.play(audio_data, audio.SAMPLE_RATE)  # Uses PulseAudio default
                sd.wait()
            except Exception as e:
                log(f"Playback error: {e}", "error")

        log("Transcribing...")

        # Prepare audio for Whisper (downsample to 16kHz)
        audio_16k = audio.prepare_for_whisper(audio_data)

        try:
            # Transcribe
            text = transcription.transcribe(audio_16k)

            if text:
                log(f"Raw transcription: '{text}'")

                # Process voice commands if enabled
                if config.voice_commands_enabled:
                    processed_text, should_validate = process_voice_commands(text)
                    log(
                        f"After command processing: '{processed_text}' (validate={should_validate})"
                    )
                else:
                    processed_text = text
                    should_validate = False

                if processed_text:
                    # Paste the text
                    paste_text(processed_text, press_enter=should_validate)

                    # Add to history (original text)
                    history.add_to_history(text)

                    # Success notification
                    send_notification(
                        "MySuperWhisper",
                        f"Text pasted ({len(processed_text)} chars)",
                        "dialog-ok",
                    )
                elif should_validate:
                    # Just validation keyword without text -> press Enter
                    press_enter_key()
                    send_notification("MySuperWhisper", "Enter key sent", "dialog-ok")
            else:
                log("Nothing detected.", "warning")
                play_sound("error")
                send_notification(
                    "MySuperWhisper", "No text detected", "dialog-warning"
                )

        except Exception as e:
            log(f"Transcription error: {e}", "error")
            play_sound("error")
            send_notification("MySuperWhisper", f"Error: {e}", "dialog-error")

        # Return to idle state
        tray.update_tray("idle")


def save_config():
    """Save configuration."""
    config.save()


def sleep_monitor_worker():
    """Monitor for inactivity and put app to sleep."""
    global _is_sleeping, _is_model_loaded
    while True:
        time.sleep(10)
        now = time.time()
        inactive_duration = now - _last_activity_time

        if not _is_sleeping and not audio.is_currently_recording():
            if inactive_duration > AUTO_SLEEP_TIMEOUT:
                mins = int(AUTO_SLEEP_TIMEOUT / 60)
                log(f"Entering sleep mode due to inactivity ({mins}m)...")
                _is_sleeping = True
                # Deactivate mic after inactivity
                audio.stop_stream()

        if (
            config.unload_model_after_inactivity
            and _is_model_loaded
            and not audio.is_currently_recording()
        ):
            if inactive_duration > MODEL_UNLOAD_TIMEOUT:
                mins = int(MODEL_UNLOAD_TIMEOUT / 60)
                log(f"Unloading model due to inactivity ({mins}m)...")
                transcription.unload_model()
                _is_model_loaded = False
                tray.update_tray("sleeping")


def startup_worker():
    """
    Startup initialization running in background.
    Loads model and starts audio stream.
    """
    # Load Whisper model
    transcription.load_model()

    # Start audio processing thread
    processing_thread = threading.Thread(target=audio_processing_loop, daemon=True)
    processing_thread.start()

    # Start audio stream (uses PulseAudio default source)
    audio.start_stream()

    # Setup keyboard callbacks and start listener
    keyboard.set_callbacks(
        on_double_ctrl=on_double_ctrl,
        on_triple_ctrl=on_triple_ctrl,
        is_recording=audio.is_currently_recording,
    )
    keyboard.start_listener()

    log("Ready! Press Double Ctrl to start/stop recording.")
    log("The icon has been added to the notification area (system tray).")
    log("Right-click the icon to change microphone or test audio level.")

    tray.update_tray("idle")


def on_quit():
    """Handle application quit."""
    os._exit(0)


def signal_handler(signum, frame):
    """Handle signals for external control."""
    if signum == signal.SIGUSR1:
        log("Received SIGUSR1, toggling recording...")
        on_double_ctrl()
    elif signum == signal.SIGUSR2:
        log("Received SIGUSR2, ensuring recording is STARTED")
        if not audio.is_currently_recording():
            on_double_ctrl()
    elif signum == signal.SIGRTMIN:
        log("Received SIGRTMIN, ensuring recording is STOPPED")
        if audio.is_currently_recording():
            on_double_ctrl()


def check_single_instance():
    """
    Ensure only one instance is running using lock file.
    Returns True if this is the only instance, False otherwise.
    """
    import fcntl

    lock_file = "/tmp/mysuperwhisper.lock"

    try:
        # Open the lock file (create if runs first)
        f = open(lock_file, "w")
        # Try to acquire an exclusive lock
        fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)

        # Write PID to lock file
        f.write(str(os.getpid()))
        f.flush()

        # Keep file open to hold lock
        global _instance_lock_file
        _instance_lock_file = f
        return True
    except IOError:
        return False


def get_running_pid():
    """Get the PID of the running instance."""
    lock_file = "/tmp/mysuperwhisper.lock"
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                content = f.read().strip()
                if content:
                    return int(content)
        except Exception:
            pass
    return None


def main():
    """Main entry point."""
    global args

    # Parse arguments first
    args = parse_args()

    # Check if we should just toggle/start/stop an existing instance
    if args.toggle or args.start or args.stop:
        pid = get_running_pid()
        if pid:
            try:
                sig = signal.SIGUSR1
                action = "toggle"
                if args.start:
                    sig = signal.SIGUSR2
                    action = "start"
                elif args.stop:
                    sig = signal.SIGRTMIN
                    action = "stop"

                os.kill(pid, sig)
                print(f"Sent {action} signal to instance with PID {pid}")
                sys.exit(0)
            except ProcessLookupError:
                print("Lock file exists but process not found.")
            except Exception as e:
                print(f"Error sending signal: {e}")
                sys.exit(1)
        else:
            print("MySuperWhisper is not running.")
            sys.exit(1)

    # Check for existing instance
    if not check_single_instance():
        print("MySuperWhisper is already running!")
        send_notification(
            "MySuperWhisper", "Application is already running.", "dialog-information"
        )
        sys.exit(0)

    log("Starting MySuperWhisper")
    log(f"Config directory: {CONFIG_DIR}")
    log(f"Log file: {LOG_FILE}")

    # Load configuration
    config.load()

    # Restore PulseAudio devices from config
    config.restore_audio_devices()

    # Setup signal handlers
    signal.signal(signal.SIGUSR1, signal_handler)
    signal.signal(signal.SIGUSR2, signal_handler)
    signal.signal(signal.SIGRTMIN, signal_handler)

    # Load history
    history.load_history()

    # Setup tray callbacks
    tray.set_callbacks(on_quit=on_quit, save_config=save_config)

    # Create tray icon
    tray.create_tray_icon()

    # Start background initialization
    threading.Thread(target=startup_worker, daemon=True).start()

    # Start device monitoring
    threading.Thread(target=tray.device_monitor_worker, daemon=True).start()

    # Start sleep monitor
    threading.Thread(target=sleep_monitor_worker, daemon=True).start()

    # Run tray event loop (blocking)
    tray.run_tray()


if __name__ == "__main__":
    main()
