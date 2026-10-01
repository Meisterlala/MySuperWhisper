"""Per-recording ownership and reconciliation of provisional dictation text."""

import threading

import regex

from .config import log
from .paste import focused_target, type_live_edit, press_enter_key


def _clusters(text):
    """Backspace deletes displayed characters, not UTF-8 bytes or code points."""
    return regex.findall(r"\X", text)


class LiveTypingSession:
    def __init__(self, target):
        self.target = target
        self.text = ""
        self.lock = threading.Lock()
        self.stopped = False
        self.finished = False
        self.lost_focus = False

    def _apply(self, text):
        if self.lost_focus or focused_target() != self.target:
            self.lost_focus = True
            log("Live typing stopped: target focus changed or cannot be verified", "warning")
            return False
        old, new = _clusters(self.text), _clusters(text)
        common = 0
        while common < min(len(old), len(new)) and old[common] == new[common]:
            common += 1
        if old != new:
            try:
                type_live_edit(len(old) - common, "".join(new[common:]))
            except Exception as exc:
                # Injection may have partly succeeded; never issue speculative deletes.
                self.lost_focus = True
                log(f"Live typing injection failed: {exc}", "error")
                return False
        self.text = text
        return True

    def preview(self, text):
        with self.lock:
            if not self.stopped and not self.finished:
                self._apply(text)

    def stop(self):
        with self.lock:
            self.stopped = True

    def abandon(self):
        """Stop editing after a transcription failure; leave any draft in place."""
        with self.lock:
            self.stopped = True
            self.finished = True

    def finish(self, text, press_enter=False):
        """Replace provisional output with the final processed transcript once."""
        with self.lock:
            if self.finished:
                return False
            self.stopped = True
            applied = self._apply(text)
            if applied and press_enter:
                # Check focus once more immediately before a potentially destructive Enter.
                if focused_target() == self.target:
                    press_enter_key()
                else:
                    applied = False
            self.finished = True
            return applied
