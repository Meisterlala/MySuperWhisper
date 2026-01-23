"""
Transcription history management for MySuperWhisper.
Stores recent transcriptions for quick access via Triple Ctrl.
"""

import json
import threading
import time
import tkinter as tk
from datetime import datetime
from .config import log, HISTORY_FILE
from .paste import paste_text
from .notifications import send_notification

# Maximum number of entries to keep
MAX_HISTORY = 20

# Global state
transcription_history = []
history_popup_open = False


def load_history():
    """Load transcription history from JSON file."""
    global transcription_history
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                transcription_history = json.load(f)
                # Limit to MAX_HISTORY entries
                transcription_history = transcription_history[-MAX_HISTORY:]
                log(f"History loaded: {len(transcription_history)} entries")
    except Exception as e:
        log(f"Error loading history: {e}", "error")
        transcription_history = []


def save_history():
    """Save transcription history to JSON file."""
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(transcription_history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Error saving history: {e}", "error")


def add_to_history(text):
    """
    Add a transcription to history.

    Args:
        text: The transcribed text to store
    """
    global transcription_history

    entry = {
        "text": text,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    transcription_history.append(entry)

    # Limit to MAX_HISTORY
    if len(transcription_history) > MAX_HISTORY:
        transcription_history = transcription_history[-MAX_HISTORY:]

    save_history()


def show_history_popup():
    """
    Display a popup window to select from transcription history.

    The popup shows recent transcriptions with timestamps.
    Use arrow keys to navigate, Enter to select and paste, Escape to close.
    """
    global history_popup_open

    if not transcription_history:
        send_notification("MySuperWhisper", "History is empty", "dialog-information")
        return

    history_popup_open = True
    selected_text = [None]  # List to allow modification in closures

    try:
        root = tk.Tk()
        root.title("MySuperWhisper History")
        root.attributes('-topmost', True)
        root.configure(bg='#2d2d2d')

        # Center window on screen
        window_width = 600
        window_height = 400
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Title label
        title_label = tk.Label(
            root,
            text="Transcription History (↑↓ + Enter)",
            font=('Sans', 12, 'bold'),
            bg='#2d2d2d',
            fg='#ffffff',
            pady=10
        )
        title_label.pack(fill='x')

        # Frame for list
        frame = tk.Frame(root, bg='#2d2d2d')
        frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Scrollbar
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')

        # Listbox
        listbox = tk.Listbox(
            frame,
            font=('Sans', 10),
            bg='#3d3d3d',
            fg='#ffffff',
            selectbackground='#5294e2',
            selectforeground='#ffffff',
            highlightthickness=0,
            yscrollcommand=scrollbar.set
        )
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)

        # Fill list (most recent first)
        for entry in reversed(transcription_history):
            text = entry['text']
            timestamp = entry['timestamp']
            # Truncate long text
            display_text = text[:60] + "..." if len(text) > 60 else text
            # Replace newlines for display
            display_text = display_text.replace('\n', ' ')
            listbox.insert('end', f"[{timestamp}] {display_text}")

        # Select first item
        if listbox.size() > 0:
            listbox.selection_set(0)
            listbox.activate(0)
            listbox.focus_set()

        def on_select(event=None):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                # Index is reversed since we display most recent first
                real_index = len(transcription_history) - 1 - index
                selected_text[0] = transcription_history[real_index]['text']
            root.destroy()

        def on_escape(event=None):
            root.destroy()

        # Bindings
        root.bind('<Return>', on_select)
        root.bind('<Escape>', on_escape)
        listbox.bind('<Double-Button-1>', on_select)

        # Help label at bottom
        help_label = tk.Label(
            root,
            text="Enter: Paste  |  Escape: Close",
            font=('Sans', 9),
            bg='#2d2d2d',
            fg='#888888',
            pady=5
        )
        help_label.pack(fill='x')

        root.mainloop()

    except Exception as e:
        log(f"History popup error: {e}", "error")
    finally:
        history_popup_open = False

    # Paste selected text
    if selected_text[0]:
        # Small delay to let focus return
        time.sleep(0.1)
        paste_text(selected_text[0])
        log(f"History: pasted text ({len(selected_text[0])} chars)")


def is_popup_open():
    """Check if history popup is currently open."""
    return history_popup_open


def open_history_popup_async():
    """Open history popup in a separate thread."""
    if not history_popup_open:
        threading.Thread(target=show_history_popup, daemon=True).start()
