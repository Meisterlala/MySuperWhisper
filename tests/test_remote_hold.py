"""The physical hold shortcut must survive unrelated virtual key releases."""

from unittest.mock import patch

import pytest

import remote_control


class Device:
    def __init__(self, states):
        self.states = iter(states)
        self.closed = False

    def active_keys(self):
        return next(self.states)

    def close(self):
        self.closed = True


def test_wait_for_held_key_ignores_other_key_changes():
    device = Device([[188], [188, 30], [188], []])
    with patch.object(remote_control, "_held_key_devices", return_value=(188, [device])), \
         patch.object(remote_control.time, "sleep") as sleep:
        assert remote_control.wait_for_key_release() is True
    assert sleep.call_count == 3
    assert device.closed


def test_held_key_discovery_ignores_modifiers_and_virtual_devices():
    from evdev import ecodes

    physical = Device([[ecodes.KEY_LEFTSHIFT, ecodes.KEY_F18]])
    physical.phys = "usb-keyboard"
    physical.capabilities = lambda: {ecodes.EV_KEY: [ecodes.KEY_F18]}
    virtual = Device([[ecodes.KEY_A]])
    virtual.phys = ""
    virtual.capabilities = lambda: {ecodes.EV_KEY: [ecodes.KEY_A]}
    with patch("evdev.list_devices", return_value=["physical", "virtual"]), \
         patch("evdev.InputDevice", side_effect=[physical, virtual]):
        key, devices = remote_control._held_key_devices()
    assert key == ecodes.KEY_F18
    assert devices == [physical]
    assert virtual.closed
    physical.close()


def test_hold_stops_even_if_release_watcher_fails():
    with patch.object(remote_control, "send_command", side_effect=[True, True]) as send, \
         patch.object(remote_control, "wait_for_key_release", side_effect=OSError("device unplugged")):
        with pytest.raises(OSError, match="device unplugged"):
            remote_control.hold_key()
    assert [call.args[0] for call in send.call_args_list] == ["start", "stop"]
