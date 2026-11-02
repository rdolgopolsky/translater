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
    if modifiers == 0 or len(keys) != 1 or len(keys[0]) != 1 or keys[0] not in "abcdefghijklmnopqrstuvwxyz0123456789":
        raise ValueError(f"Непідтримувана клавіша в хоткеї: {hotkey}")
    # Windows VK_A..VK_Z and VK_0..VK_9 do not depend on the input language.
    return modifiers, ord(keys[0].upper())


def format_hotkey_display(hotkey):
    """Format a normalized hotkey string like 'ctrl+shift+q' as 'Ctrl+Shift+Q'."""
    canonical = {"control": "Ctrl", "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win", "windows": "Win"}
    parts = [p.strip() for p in (hotkey or "").split("+") if p.strip()]
    return "+".join(canonical.get(p.lower(), p.upper()) for p in parts)


def _extract_event_modifiers(event, is_release=False):
    """Return active modifier names ('ctrl', 'alt', 'shift', 'win') from a Tk KeyPress event or Win32 state."""
    mods = []
    state = getattr(event, "state", 0) or 0
    keycode = getattr(event, "keycode", 0)
    # In Windows Tk: 0x0001 = Shift, 0x0004 = Ctrl, 0x20000 = Alt (0x0008 is NumLock!)
    ctrl = bool(state & 0x0004)
    alt = bool(state & 0x20000)
    shift = bool(state & 0x0001)
    win = False
    try:
        import win32api
        import win32con
        ctrl = ctrl or (win32api.GetKeyState(win32con.VK_CONTROL) < 0)
        alt = alt or (win32api.GetKeyState(win32con.VK_MENU) < 0)
        shift = shift or (win32api.GetKeyState(win32con.VK_SHIFT) < 0)
        win = (win32api.GetKeyState(win32con.VK_LWIN) < 0) or (win32api.GetKeyState(win32con.VK_RWIN) < 0)
    except Exception:
        pass
    if is_release:
        if keycode == 17:
            ctrl = False
        elif keycode == 18:
            alt = False
        elif keycode == 16:
            shift = False
        elif keycode in (91, 92):
            win = False
    if ctrl:
        mods.append("ctrl")
    if alt:
        mods.append("alt")
    if shift:
        mods.append("shift")
    if win:
        mods.append("win")
    return mods


def create_hotkey_recorder(parent, initial_hotkey, prompt_text="Натисніть комбінацію...", on_record_start=None, on_record_end=None):
    """Create a human-friendly button that captures a key combination when clicked."""
    import customtkinter as ctk

    state = {"value": (initial_hotkey or "ctrl+q").strip().lower(), "recording": False}
    toplevel = parent.winfo_toplevel()

    btn = ctk.CTkButton(
        parent,
        text=format_hotkey_display(state["value"]),
        height=30,
        fg_color="#2b2b2b",
        hover_color="#383838",
        border_width=1,
        border_color="#555555",
        font=("Arial", 13, "bold"),
    )

    def stop_recording(restore=True, notify_end=True):
        if not state["recording"]:
            return
        state["recording"] = False
        if getattr(toplevel, "_active_hotkey_recorder", None) is stop_recording:
            toplevel._active_hotkey_recorder = None
        if btn.winfo_exists():
            btn.configure(
                text=format_hotkey_display(state["value"]),
                fg_color="#2b2b2b",
                border_color="#555555",
                text_color=("gray10", "gray90"),
            )
        if notify_end and on_record_end:
            on_record_end()

    def start_recording():
        if state["recording"]:
            stop_recording(restore=True)
            return
        prev_stop = getattr(toplevel, "_active_hotkey_recorder", None)
        if callable(prev_stop):
            prev_stop(restore=True, notify_end=False)
        state["recording"] = True
        toplevel._active_hotkey_recorder = stop_recording
        if on_record_start:
            on_record_start()
        btn.configure(
            text=prompt_text,
            fg_color="#1f538d",
            border_color="#4da6ff",
            text_color="white",
        )
        toplevel.focus_set()

    def on_key_press(event):
        if not state["recording"]:
            return None
        keycode = getattr(event, "keycode", 0)
        # Escape cancels recording
        if keycode == 27:
            stop_recording(restore=True)
            return "break"

        mods = _extract_event_modifiers(event)
        # Modifier-only keycodes: Shift(16), Ctrl(17), Alt(18), LWin(91), RWin(92)
        if keycode in (16, 17, 18, 91, 92):
            if mods:
                preview = "+".join(format_hotkey_display(m) for m in mods) + "+..."
                btn.configure(text=preview)
            return "break"

        # Physical A-Z (65..90) or 0-9 (48..57)
        if (65 <= keycode <= 90) or (48 <= keycode <= 57):
            if not mods:
                return "break"
            key_char = chr(keycode).lower()
            candidate = "+".join(mods + [key_char])
            try:
                parse_hotkey(candidate)
            except ValueError:
                return "break"
            state["value"] = candidate
            stop_recording(restore=False)
            return "break"

        return "break"

    def on_key_release(event):
        if not state["recording"]:
            return None
        mods = _extract_event_modifiers(event, is_release=True)
        if mods:
            btn.configure(text="+".join(format_hotkey_display(m) for m in mods) + "+...")
        else:
            btn.configure(text=prompt_text)
        return "break"

    btn.configure(command=start_recording)
    toplevel.bind("<KeyPress>", on_key_press, add="+")
    toplevel.bind("<KeyRelease>", on_key_release, add="+")

    btn.get = lambda: state["value"]
    btn.set = lambda value: (
        state.__setitem__("value", (value or "").strip().lower()),
        btn.configure(text=format_hotkey_display(state["value"])),
    )
    btn._handle_key_press = on_key_press
    btn._start_recording = start_recording
    btn._stop_recording = stop_recording
    return btn


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
        # Leave AltGr and other modified combinations to Tk (0x20000 is Alt on Windows Tk; 0x0008 is NumLock).
        if event.state & 0x20000:
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
