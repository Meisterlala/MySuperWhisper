#!/usr/bin/env python3
"""
MySuperWhisper - Global Voice Dictation Tool

A Linux desktop application that provides global voice-to-text transcription
using IBM Granite Speech models. Press Double Ctrl to start/stop recording,
and the transcribed text is automatically typed into any application.

Features:
- Global hotkey (Double Ctrl) works in any application
- Final transcription with Granite Speech 4.1 2B
- Live preview with Granite Speech 4.1 2B NAR when available
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
import re
import signal
import sys
import threading
import time

import numpy as np

from . import audio, history, keyboard, transcription, tray
from .config import CONFIG_DIR, LOG_FILE, config, log
from .notifications import play_sound, send_live_notification, send_notification
from .paste import paste_text, press_enter_key
from .voice_commands import process_voice_commands

# Processing queue
processing_queue = queue.Queue()

# Command line arguments
args = None

# Chunked ahead decoding tuning
CHUNK_CHECK_INTERVAL = 1.0
CHUNK_MIN_COMMIT_SECONDS = 8.0
CHUNK_TAIL_SECONDS = 4.0
CHUNK_OVERLAP_SECONDS = 1.5
CHUNK_MAX_WINDOW_SECONDS = 45.0
CHUNK_SILENCE_THRESHOLD = 0.015
CHUNK_SILENCE_MIN_SECONDS = 0.35


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
_is_model_loaded = False
_is_model_loading = False
_model_load_error = None
_chunked_decode_state = None
_chunked_decode_thread = None

# Inactivity timeouts (seconds)
AUTO_SLEEP_TIMEOUT = 15
MODEL_UNLOAD_TIMEOUT = 60 * 30


def update_activity():
    """Update last activity timestamp and wake up if sleeping."""
    global _last_activity_time, _is_sleeping, _is_model_loaded
    _last_activity_time = time.time()

    if _is_sleeping:
        log("Waking up from sleep mode...")
        _is_sleeping = False
        audio.start_stream()
        tray.update_tray("idle")


def on_double_ctrl():
    """Handle Double Ctrl: toggle recording."""
    update_activity()
    if audio.is_currently_recording():
        stop_and_process()
    else:
        # If model is not loaded, start loading it in background while recording
        if not _is_model_loaded and not _is_model_loading:
            log("Starting record while loading model...")
            threading.Thread(target=lazy_load_model, daemon=True).start()
        start_recording()


def lazy_load_model():
    """Load model in background without blocking recording."""
    global _is_model_loaded, _is_model_loading, _model_load_error
    if _is_model_loaded or _is_model_loading:
        return

    _is_model_loading = True
    _model_load_error = None
    log("Background model loading started...")
    try:
        transcription.load_model()
        _is_model_loaded = True
        tray.refresh_menu()
        log("Background model loading complete.")
    except Exception as exc:
        _is_model_loaded = False
        _model_load_error = exc
        transcription.unload_model()
        tray.refresh_menu()
        tray.update_tray("sleeping")
        log(f"Background model loading failed: {exc}", "error")
    finally:
        _is_model_loading = False


def on_triple_ctrl():
    """Handle Triple Ctrl: open history popup."""
    update_activity()
    if not history.is_popup_open():
        history.open_history_popup_async()


def _make_chunked_decode_state():
    return {
        "lock": threading.Lock(),
        "transcript": "",
        "committed_end": 0,
        "inflight": False,
    }


def _merge_chunk_text(existing_text, new_text):
    """Merge overlapping chunk transcripts using suffix/prefix word overlap."""
    existing_text = (existing_text or "").strip()
    new_text = (new_text or "").strip()

    if not existing_text:
        return new_text
    if not new_text:
        return existing_text

    existing_words = re.findall(r"\S+", existing_text)
    new_word_matches = list(re.finditer(r"\S+", new_text))
    new_words = [match.group(0) for match in new_word_matches]
    max_overlap = min(len(existing_words), len(new_words), 40)

    for overlap in range(max_overlap, 0, -1):
        existing_slice = " ".join(existing_words[-overlap:]).lower()
        new_slice = " ".join(new_words[:overlap]).lower()
        if existing_slice == new_slice:
            if overlap >= len(new_word_matches):
                return existing_text

            remaining_text = new_text[new_word_matches[overlap].start():]
            separator = ""
            if existing_text and remaining_text:
                if not existing_text[-1].isspace() and not remaining_text[0].isspace():
                    separator = " "
            return f"{existing_text}{separator}{remaining_text}".strip()

    if existing_text.lower().endswith(new_text.lower()):
        return existing_text

    separator = " "
    if existing_text and new_text:
        if existing_text.endswith("\n") or new_text.startswith("\n"):
            separator = ""
        elif existing_text.endswith((".", "!", "?")) and new_text.startswith("\n\n"):
            separator = ""

    return f"{existing_text}{separator}{new_text}".strip()


def _find_silence_chunk_boundary(audio_16k, committed_end):
    """Pick the latest safe silence boundary before the live tail."""
    tail_samples = int(CHUNK_TAIL_SECONDS * 16000)
    min_commit_samples = int(CHUNK_MIN_COMMIT_SECONDS * 16000)
    max_window_samples = int(CHUNK_MAX_WINDOW_SECONDS * 16000)
    silence_samples = int(CHUNK_SILENCE_MIN_SECONDS * 16000)

    available_end = len(audio_16k) - tail_samples
    if available_end - committed_end < min_commit_samples:
        return None

    search_start = committed_end + min_commit_samples
    region = np.abs(audio_16k[search_start:available_end]) <= CHUNK_SILENCE_THRESHOLD
    if region.size >= silence_samples:
        padded = np.concatenate((np.array([0], dtype=np.int8), region.astype(np.int8), np.array([0], dtype=np.int8)))
        transitions = np.diff(padded)
        starts = np.where(transitions == 1)[0]
        ends = np.where(transitions == -1)[0]
        valid = np.where((ends - starts) >= silence_samples)[0]
        if valid.size:
            return search_start + int(starts[valid[-1]])

    if available_end - committed_end >= max_window_samples:
        return available_end

    return None


def chunked_decode_worker(session_state):
    """Background chunk transcription during recording."""
    log("Chunked preemptive decoding worker started", "debug")
    overlap_samples = int(CHUNK_OVERLAP_SECONDS * 16000)

    while _is_recording:
        time.sleep(CHUNK_CHECK_INTERVAL)

        if not _is_model_loaded:
            continue

        with session_state["lock"]:
            if session_state["inflight"]:
                continue
            committed_end = session_state["committed_end"]
            session_state["inflight"] = True

        try:
            audio_data = audio.get_current_buffer()
            if audio_data is None:
                continue

            audio_16k = audio.prepare_for_transcription(audio_data)
            boundary = _find_silence_chunk_boundary(audio_16k, committed_end)
            if boundary is None:
                continue

            chunk_start = max(committed_end - overlap_samples, 0)
            chunk_audio = audio_16k[chunk_start:boundary]
            if len(chunk_audio) < 16000:
                continue

            log(
                "Chunked preemptive decoding: transcribing "
                f"{chunk_start / 16000.0:.1f}s -> {boundary / 16000.0:.1f}s",
                "debug",
            )

            text = transcription.transcribe(chunk_audio)
            if not text:
                with session_state["lock"]:
                    session_state["committed_end"] = boundary
                log("Chunked preemptive decoding: chunk produced no text", "debug")
                continue

            with session_state["lock"]:
                session_state["transcript"] = _merge_chunk_text(
                    session_state["transcript"], text
                )
                session_state["committed_end"] = boundary
                log(
                    "Chunked preemptive decoding committed "
                    f"{boundary / 16000.0:.1f}s of audio.",
                )
        except Exception as e:
            log(f"Chunked preemptive decoding error: {e}", "debug")
        finally:
            with session_state["lock"]:
                session_state["inflight"] = False

    log("Chunked preemptive decoding worker stopped", "debug")


def _collect_chunked_decode_result(audio_data):
    """Capture the background-decoded prefix for final stitching."""
    global _chunked_decode_state

    if not config.chunked_ahead_decoding_enabled or _chunked_decode_state is None:
        _chunked_decode_state = None
        return None

    with _chunked_decode_state["lock"]:
        prefetched = {
            "transcript": _chunked_decode_state["transcript"],
            "committed_end": _chunked_decode_state["committed_end"],
        }

    _chunked_decode_state = None

    if not prefetched["transcript"] or prefetched["committed_end"] <= 0:
        return None

    total_samples_16k = len(audio.prepare_for_transcription(audio_data))
    if prefetched["committed_end"] >= total_samples_16k:
        prefetched["committed_end"] = max(total_samples_16k - 1, 0)

    log(
        "Chunked preemptive decoding prepared "
        f"{prefetched['committed_end'] / 16000.0:.1f}s ahead of stop"
    )

    return prefetched


def _transcribe_final_audio(audio_16k, prefetched=None):
    """Transcribe full audio or stitch in background-decoded chunks."""
    if not prefetched:
        return transcription.transcribe(audio_16k)

    overlap_samples = int(CHUNK_OVERLAP_SECONDS * 16000)
    tail_start = max(prefetched["committed_end"] - overlap_samples, 0)
    tail_audio = audio_16k[tail_start:]
    log(
        "Chunked preemptive decoding: finishing tail from "
        f"{tail_start / 16000.0:.1f}s to {len(audio_16k) / 16000.0:.1f}s",
        "debug",
    )
    tail_text = transcription.transcribe(tail_audio) if len(tail_audio) >= 1600 else ""
    merged_text = _merge_chunk_text(prefetched["transcript"], tail_text)
    log("Chunked preemptive decoding: stitched prefetched chunks with final tail", "debug")
    return merged_text.strip()


def start_recording():
    """Start voice recording."""
    global _is_recording, _live_preview_thread, _chunked_decode_state, _chunked_decode_thread
    _is_recording = True

    audio.start_recording()
    _chunked_decode_state = None

    # Do notifications in background
    def _notify():
        play_sound("start")
        tray.update_tray("recording")
        send_notification("MySuperWhisper", "Listening...", "audio-input-microphone")

    threading.Thread(target=_notify, daemon=True).start()

    # Start live preview loop
    _live_preview_thread = threading.Thread(target=live_preview_worker, daemon=True)
    _live_preview_thread.start()

    if config.chunked_ahead_decoding_enabled:
        _chunked_decode_state = _make_chunked_decode_state()
        _chunked_decode_thread = threading.Thread(
            target=chunked_decode_worker,
            args=(_chunked_decode_state,),
            daemon=True,
        )
        _chunked_decode_thread.start()


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
    processing_queue.put(
        {
            "audio_data": audio_data,
            "prefetched": _collect_chunked_decode_result(audio_data),
        }
    )


def live_preview_worker():
    """Worker thread for live transcription preview."""
    log("Live preview worker started", "debug")
    last_preview_time = time.time()

    while _is_recording:
        time.sleep(0.05)
        if not config.live_preview_enabled:
            break

        now = time.time()

        # Update preview every 0.6 seconds if we have audio and model is loaded
        if now - last_preview_time >= 0.6:
            if not _is_model_loaded:
                # Suspend live output until model is loaded
                continue

            audio_data = audio.get_current_buffer()
            if audio_data is not None:
                audio_len = len(audio_data)
                if audio_len > 32000:  # Min ~0.7s of audio
                    try:
                        audio_16k = audio.prepare_for_transcription(audio_data)
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
        work_item = processing_queue.get()
        if isinstance(work_item, dict):
            audio_data = work_item["audio_data"]
            prefetched = work_item.get("prefetched")
        else:
            audio_data = work_item
            prefetched = None

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

        # Wait for model to be loaded if it's still loading
        if not _is_model_loaded:
            log("Waiting for model to load before transcribing...", "debug")
            while _is_model_loading and not _model_load_error:
                time.sleep(0.05)
            if not _is_model_loaded:
                if _model_load_error:
                    log(f"Skipping transcription because model failed to load: {_model_load_error}", "error")
                else:
                    log("Skipping transcription because model is not loaded.", "error")
                continue

        # Prepare audio for Granite speech transcription (downsample to 16kHz)
        audio_16k = audio.prepare_for_transcription(audio_data)

        try:
            # Transcribe
            text = _transcribe_final_audio(audio_16k, prefetched=prefetched)

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


def unload_model_on_demand():
    """Unload the model from the tray and keep main state in sync."""
    global _is_model_loaded, _is_model_loading, _model_load_error
    unloaded = transcription.unload_model()
    _is_model_loaded = False
    _is_model_loading = False
    _model_load_error = None
    return unloaded


def sleep_monitor_worker():
    """Monitor for inactivity and put app to sleep."""
    global _is_sleeping, _is_model_loaded, _is_model_loading, _model_load_error
    while True:
        time.sleep(10)
        now = time.time()
        inactive_duration = now - _last_activity_time

        if not _is_sleeping and not audio.is_currently_recording():
            if inactive_duration > AUTO_SLEEP_TIMEOUT:
                mins = AUTO_SLEEP_TIMEOUT / 60.0
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
                mins = MODEL_UNLOAD_TIMEOUT / 60.0
                log(f"Unloading model due to inactivity ({mins}m)...")
                transcription.unload_model()
                _is_model_loaded = False
                _is_model_loading = False
                _model_load_error = None
                tray.refresh_menu()
                tray.update_tray("sleeping")


def startup_worker():
    """
    Startup initialization running in background.
    Prepares system and starts audio stream.
    Model is NOT loaded on startup to save resources.
    """
    # Start audio processing thread
    processing_thread = threading.Thread(target=audio_processing_loop, daemon=True)
    processing_thread.start()

    # Start audio stream (uses PulseAudio default source)
    audio.start_stream()

    # Setup keyboard callbacks and start listener
    keyboard.set_callbacks(
        on_record_hotkey=on_double_ctrl,
        on_history_hotkey=on_triple_ctrl,
        is_recording=audio.is_currently_recording
    )
    keyboard.start_listener()

    # Log ready message with actual hotkey
    from .keyboard import _get_hotkey_description
    hotkey_desc = _get_hotkey_description(config.record_hotkey, config.record_press_count)
    log(f"Ready! Press {hotkey_desc} to start/stop recording.")
    log("The icon has been added to the notification area (system tray).")
    log("Right-click the icon to change microphone or test audio level.")

    # Status is sleeping since model is not loaded
    tray.update_tray("sleeping")


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
    tray.set_callbacks(
        on_quit=on_quit,
        save_config=save_config,
        unload_model=unload_model_on_demand,
    )

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
