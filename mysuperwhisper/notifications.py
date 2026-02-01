"""
Notification system for MySuperWhisper.
Handles system notifications (notify-send) and audio feedback (beeps).
"""

import io
import os
import subprocess
import tempfile
import threading
import wave
import numpy as np
from .config import log, config


def send_live_notification(text):
    """
    Send or update a persistent live transcription notification.
    Bypasses the global system_notifications_enabled setting.
    """
    try:
        cmd = [
            "notify-send",
            "-i", "audio-input-microphone",
            "-a", "MySuperWhisper",
            "-h", "string:x-canonical-private-synchronous:mysuperwhisper-live",
            "-h", "int:transient:1",
            "-t", "2000",
            "MySuperWhisper (Live)", text
        ]
        subprocess.Popen(cmd)
    except Exception as e:
        log(f"Live notification error: {e}", "error")


def send_notification(title, message, icon="dialog-information"):
    """
    Send a standard system notification via notify-send.
    Respects the global system_notifications_enabled setting.
    """
    if not config.system_notifications_enabled:
        return

    try:
        cmd = [
            "notify-send",
            "-i", icon,
            "-a", "MySuperWhisper",
            "-t", "3000",
            title, message
        ]
        subprocess.Popen(cmd)
    except FileNotFoundError:
        log("notify-send not found. Install libnotify-bin.", "warning")
    except Exception as e:
        log(f"Notification error: {e}", "error")


def _generate_beep_wav(frequency, duration_ms, volume=0.5):
    """
    Generate a beep sound as WAV data.

    Args:
        frequency: Frequency in Hz
        duration_ms: Duration in milliseconds
        volume: Volume from 0.0 to 1.0

    Returns:
        bytes: WAV file data
    """
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, n_samples, False)

    # Generate sine wave
    wave_data = np.sin(2 * np.pi * frequency * t) * volume

    # Soft envelope (fade in/out) to avoid clicks
    fade_samples = int(sample_rate * 0.01)  # 10ms fade
    if len(wave_data) > fade_samples * 2:
        wave_data[:fade_samples] *= np.linspace(0, 1, fade_samples)
        wave_data[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    # Convert to int16 for WAV
    wave_data = (wave_data * 32767).astype(np.int16)

    # Create WAV file in memory
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16 bits
        wf.setframerate(sample_rate)
        wf.writeframes(wave_data.tobytes())

    return buffer.getvalue()


def play_sound(sound_type):
    """
    Play a notification sound if enabled.

    Uses paplay (PulseAudio) for reliable playback.
    Runs in a separate thread to avoid blocking.

    Args:
        sound_type: One of 'start', 'success', 'error'
    """
    if not config.sound_notifications_enabled:
        return

    # Pre-generate WAV data outside the thread if it's the 'start' sound
    # to minimize latency.
    wav_data = None
    if sound_type == "start":
        wav_data = _generate_beep_wav(600, 150)

    def _play(preloaded_wav=None):
        try:
            # Generate appropriate sound if not preloaded
            if preloaded_wav:
                wav_data_to_play = preloaded_wav
            elif sound_type == "success":
                # Higher pitched beep 880Hz 200ms
                wav_data_to_play = _generate_beep_wav(880, 200)
            elif sound_type == "error":
                # Low tone 300Hz 250ms
                wav_data_to_play = _generate_beep_wav(300, 250)
            else:
                return

            # Write to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                temp_path = f.name
                f.write(wav_data_to_play)

            # Play with paplay (PulseAudio) - most reliable
            try:
                subprocess.run(
                    ["paplay", "--latency-msec=10", temp_path],
                    capture_output=True,
                    timeout=2
                )
            except FileNotFoundError:
                # Fallback to aplay (ALSA)
                try:
                    subprocess.run(["aplay", "-q", temp_path], timeout=2)
                except FileNotFoundError:
                    pass
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except:
                    pass

        except Exception as e:
            log(f"Sound playback error: {e}", "error")

    # Play in separate thread to avoid blocking
    threading.Thread(target=_play, args=(wav_data,), daemon=True).start()
