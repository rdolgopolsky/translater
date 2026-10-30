"""Windows keyboard shortcuts that also work with a Cyrillic input layout."""

import tkinter as tk
import pyperclip


def send_ctrl_shortcut(key):
    """Send Ctrl+C/V using Windows key codes, independent of PyAutoGUI's layout cache."""
    import win32api
    import win32con
    virtual_key = ord(key.upper())
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    try:
        win32api.keybd_event(virtual_key, 0, 0, 0)
    finally:
        win32api.keybd_event(virtual_key, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def paste_text(native):
    """Insert Unicode clipboard text directly, without Tk virtual-key bindings."""
    if str(native.cget("state")) != "normal":
        return False
    try:
        text = pyperclip.paste()
    except Exception:
        try:
            text = native.clipboard_get()
        except tk.TclError:
            native.bell()
            return False
    if not text:
        return False
    if isinstance(native, tk.Text):
        if native.tag_ranges("sel"):
            native.delete("sel.first", "sel.last")
        native.insert("insert", text)
        native.see("insert")
    else:
        if native.selection_present():
            native.delete("sel.first", "sel.last")
        native.insert("insert", text)
    return True


def create_key_entry(parent, value, paste_label):
    import customtkinter as ctk
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(0, 8))
    entry = ctk.CTkEntry(row, height=30, show="*")
    entry.pack(side="left", fill="x", expand=True)
    entry.insert(0, value)
    enable_edit_shortcuts(entry)
    ctk.CTkButton(row, text=paste_label, width=80, height=30,
                  command=lambda: paste_text(entry._entry)).pack(side="right", padx=(6, 0))
    return entry


def parse_hotkey(hotkey):
    flags = {"alt": 1, "ctrl": 2, "control": 2, "shift": 4, "win": 8, "windows": 8}
    parts = hotkey.lower().replace(" ", "").split("+")
    modifiers = 0
    keys = []
    for part in parts:
        if part in flags:
            modifiers |= flags[part]
        else:
            keys.append(part)
    if len(keys) != 1 or len(keys[0]) != 1 or keys[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
        raise ValueError(f"Непідтримувана клавіша в хоткеї: {hotkey}")
    # Windows VK_A..VK_Z and VK_0..VK_9 do not depend on the input language.
    return modifiers, ord(keys[0].upper())


def enable_edit_shortcuts(widget):
    """Put physical Ctrl shortcuts before Tk's language-dependent bindings."""
    native = getattr(widget, "_entry", None)
    if native is None:
        native = getattr(widget, "_textbox", widget)
    tag = "TranslatorEditShortcuts"
    if tag not in native.bindtags():
        native.bindtags((tag,) + native.bindtags())
    if not hasattr(native, "_translator_edit_menu"):
        menu = tk.Menu(native, tearoff=False)
        menu.add_command(label="Вирізати", command=lambda: native.event_generate("<<Cut>>"))
        menu.add_command(label="Копіювати", command=lambda: native.event_generate("<<Copy>>"))
        menu.add_command(label="Вставити", command=lambda: paste_text(native))
        menu.add_separator()
        menu.add_command(label="Виділити все", command=lambda: native.event_generate("<<SelectAll>>"))
        native._translator_edit_menu = menu

        def show_menu(event):
            native.focus_set()
            editable = str(native.cget("state")) == "normal"
            menu.entryconfigure(0, state="normal" if editable else "disabled")
            menu.entryconfigure(2, state="normal" if editable else "disabled")
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        native.bind("<Button-3>", show_menu, add="+")
        native.bind("<Shift-F10>", show_menu, add="+")
    root = native._root()
    if getattr(root, "_translator_edit_shortcuts_initialized", False):
        return

    def handle(event):
        # Leave AltGr and other modified combinations to Tk.
        if event.state & 0x0008:
            return None
        action = {65: "<<SelectAll>>", 67: "<<Copy>>", 86: "<<Paste>>", 88: "<<Cut>>"}.get(event.keycode)
        if action:
            if action == "<<Paste>>":
                paste_text(event.widget)
            else:
                event.widget.event_generate(action)
            return "break"
        return None

    root.bind_class(tag, "<Control-KeyPress>", handle)
    root.bind_class(tag, "<Shift-Insert>", lambda event: (paste_text(event.widget), "break")[-1])
    root._translator_edit_shortcuts_initialized = True
