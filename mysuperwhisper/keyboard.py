"""
Keyboard shortcut handling for MySuperWhisper.
Manages Double Ctrl (record) and Triple Ctrl (history) detection.
"""

import threading
import time
from pynput import keyboard
from .config import log

# Callback functions (set by main module)
_on_double_ctrl = None
_on_triple_ctrl = None
_is_recording_callback = None

# State for Ctrl detection
_last_ctrl_time = 0
_ctrl_press_count = 0
_ctrl_action_timer = None


def set_callbacks(on_double_ctrl, on_triple_ctrl, is_recording):
    """
    Set callback functions for keyboard shortcuts.

    Args:
        on_double_ctrl: Function to call on Double Ctrl
        on_triple_ctrl: Function to call on Triple Ctrl
        is_recording: Function that returns True if currently recording
    """
    global _on_double_ctrl, _on_triple_ctrl, _is_recording_callback
    _on_double_ctrl = on_double_ctrl
    _on_triple_ctrl = on_triple_ctrl
    _is_recording_callback = is_recording


def _execute_double_ctrl_action():
    """Execute Double Ctrl action after waiting period."""
    global _ctrl_press_count, _ctrl_action_timer

    # Check that we didn't get a 3rd Ctrl in the meantime
    if _ctrl_press_count == 2 and _on_double_ctrl:
        _on_double_ctrl()

    _ctrl_press_count = 0
    _ctrl_action_timer = None


def _on_key_release(key):
    """Handle key release events."""
    global _last_ctrl_time, _ctrl_press_count, _ctrl_action_timer

    # Detect Ctrl key (Left or Right)
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        current_time = time.time()

        # If delay between releases is < 0.5s -> increment counter
        if current_time - _last_ctrl_time < 0.5:
            _ctrl_press_count += 1

            if _ctrl_press_count == 2:
                # Double Ctrl detected: wait 300ms to see if Triple Ctrl
                if _ctrl_action_timer:
                    _ctrl_action_timer.cancel()
                _ctrl_action_timer = threading.Timer(0.3, _execute_double_ctrl_action)
                _ctrl_action_timer.start()

            elif _ctrl_press_count >= 3:
                # Triple Ctrl: cancel Double Ctrl action and open history
                if _ctrl_action_timer:
                    _ctrl_action_timer.cancel()
                    _ctrl_action_timer = None
                _ctrl_press_count = 0

                # Open history (only if not recording)
                if _on_triple_ctrl and _is_recording_callback:
                    if not _is_recording_callback():
                        _on_triple_ctrl()
        else:
            # Reset counter if too much time between presses
            if _ctrl_action_timer:
                _ctrl_action_timer.cancel()
                _ctrl_action_timer = None
            _ctrl_press_count = 1

        _last_ctrl_time = current_time


def start_listener():
    """
    Start the keyboard listener.

    Returns:
        keyboard.Listener: The listener instance
    """
    listener = keyboard.Listener(on_release=_on_key_release)
    listener.start()
    log("Keyboard listener started")
    return listener


def stop_listener(listener):
    """
    Stop the keyboard listener.

    Args:
        listener: The listener instance to stop
    """
    if listener:
        listener.stop()
        log("Keyboard listener stopped")
