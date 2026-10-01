"""Live typing reconciles snapshots, never appends the final transcript twice."""

from unittest.mock import patch

from mysuperwhisper.live_typing import LiveTypingSession
from mysuperwhisper.config import Config
import mysuperwhisper.paste as paste


TARGET = ("x11", "123")


def test_live_typing_is_opt_in():
    assert Config().live_typing_enabled is False


def test_focus_detection_fails_closed_on_unsupported_wayland():
    with patch.object(paste, "detect_session_type", return_value="wayland"), \
         patch.object(paste.subprocess, "run", side_effect=FileNotFoundError):
        assert paste.focused_target() is None


def test_focus_detection_uses_hyprland_window_address():
    from unittest.mock import Mock

    result = Mock(returncode=0, stdout='{"address": "0xabc"}')
    with patch.object(paste, "detect_session_type", return_value="wayland"), \
         patch.object(paste.subprocess, "run", return_value=result):
        assert paste.focused_target() == ("hyprland", "0xabc")


def test_preview_correction_and_final_reconciliation():
    session = LiveTypingSession(TARGET)
    with patch("mysuperwhisper.live_typing.focused_target", return_value=TARGET), \
         patch("mysuperwhisper.live_typing.type_live_edit") as edit, \
         patch("mysuperwhisper.live_typing.press_enter_key") as enter:
        session.preview("I can sea")
        session.preview("I can see")
        session.stop()
        session.preview("stale preview")
        session.finish("I can see!", press_enter=True)
        session.finish("duplicate")

    assert edit.call_args_list == [
        ((0, "I can sea"),),
        ((1, "e"),),
        ((0, "!"),),
    ]
    enter.assert_called_once_with()


def test_focus_loss_does_not_delete_or_submit_elsewhere():
    session = LiveTypingSession(TARGET)
    with patch("mysuperwhisper.live_typing.focused_target", side_effect=[TARGET, ("x11", "other")]), \
         patch("mysuperwhisper.live_typing.type_live_edit") as edit, \
         patch("mysuperwhisper.live_typing.press_enter_key") as enter:
        session.preview("hello")
        session.finish("help", press_enter=True)

    edit.assert_called_once_with(0, "hello")
    enter.assert_not_called()
    assert session.text == "hello"
    assert session.finished


def test_unicode_correction_uses_grapheme_count():
    session = LiveTypingSession(TARGET)
    with patch("mysuperwhisper.live_typing.focused_target", return_value=TARGET), \
         patch("mysuperwhisper.live_typing.type_live_edit") as edit:
        session.preview("e\u0301 👍🏽")
        session.preview("e\u0301 👍")
    edit.assert_any_call(1, "👍")


def test_injection_failure_never_issues_followup_deletes():
    session = LiveTypingSession(TARGET)
    with patch("mysuperwhisper.live_typing.focused_target", return_value=TARGET), \
         patch("mysuperwhisper.live_typing.type_live_edit", side_effect=OSError("gone")) as edit:
        session.preview("hello")
        session.finish("goodbye")
    edit.assert_called_once()
    assert session.finished
