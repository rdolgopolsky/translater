import ctypes
import sys
import unittest
from unittest.mock import patch

from keyboard_shortcuts import create_key_entry, enable_edit_shortcuts, parse_hotkey, paste_text


class HotkeyParsingTests(unittest.TestCase):
    def test_default_shortcuts(self):
        self.assertEqual(parse_hotkey("ctrl+q"), (2, 0x51))
        self.assertEqual(parse_hotkey("ctrl+w"), (2, 0x57))
        for digit in range(1, 9):
            self.assertEqual(parse_hotkey(f"ctrl+alt+{digit}"), (3, ord(str(digit))))

    def test_invalid_combinations(self):
        for shortcut in ("ctrl+", "ctrl+q+w", "ctrl+unknown", "ctrl+й"):
            with self.subTest(shortcut=shortcut), self.assertRaises(ValueError):
                parse_hotkey(shortcut)


@unittest.skipUnless(sys.platform == "win32", "Windows keyboard layout regression")
class WindowsEditingTests(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        self.user32 = ctypes.windll.user32
        self.user32.LoadKeyboardLayoutW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint]
        self.user32.LoadKeyboardLayoutW.restype = ctypes.c_void_p
        self.user32.ActivateKeyboardLayout.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.user32.ActivateKeyboardLayout.restype = ctypes.c_void_p
        self.user32.GetKeyboardLayout.restype = ctypes.c_void_p
        self.original_layout = self.user32.GetKeyboardLayout(0)
        self.root = ctk.CTk()
        self.entry = ctk.CTkEntry(self.root, show="*")
        self.entry.pack()
        enable_edit_shortcuts(self.entry)
        self.root.update()
        try:
            self.original_clipboard = self.root.clipboard_get()
        except Exception:
            self.original_clipboard = None

    def tearDown(self):
        self.user32.ActivateKeyboardLayout(self.original_layout, 0)
        self.root.clipboard_clear()
        if self.original_clipboard is not None:
            self.root.clipboard_append(self.original_clipboard)
            self.root.update()
        for job in self.root.tk.call("after", "info"):
            self.root.tk.call("after", "cancel", job)
        self.root.destroy()

    def test_paste_and_select_all_in_english_and_ukrainian(self):
        for layout in ("00000409", "00000422"):
            with self.subTest(layout=layout):
                handle = self.user32.LoadKeyboardLayoutW(layout, 0)
                self.assertTrue(handle)
                self.user32.ActivateKeyboardLayout(handle, 0)
                self.assertEqual(parse_hotkey("ctrl+q"), (2, 81))
                self.entry.delete(0, "end")
                self.root.clipboard_clear()
                self.root.clipboard_append("synthetic-test-key:fx")
                self.entry._entry.focus_force()
                self.root.update()
                self.entry._entry.event_generate("<KeyPress>", keycode=86, state=4)
                self.root.update()
                self.assertEqual(self.entry.get(), "synthetic-test-key:fx")
                self.entry._entry.event_generate("<KeyPress>", keycode=65, state=4)
                self.root.update()
                self.assertTrue(self.entry._entry.selection_present())
                self.root.clipboard_clear()
                self.root.clipboard_append("replacement")
                self.entry._entry.event_generate("<KeyPress>", keycode=86, state=4)
                self.root.update()
                self.assertEqual(self.entry.get(), "replacement")

    def test_closing_another_entry_does_not_remove_shortcuts(self):
        import customtkinter as ctk
        other = ctk.CTkEntry(self.root)
        enable_edit_shortcuts(other)
        other.destroy()
        self.root.clipboard_clear()
        self.root.clipboard_append("still-works")
        self.entry._entry.focus_force()
        self.root.update()
        self.entry._entry.event_generate("<KeyPress>", keycode=86, state=4)
        self.root.update()
        self.assertEqual(self.entry.get(), "still-works")

    def test_right_click_opens_menu_and_menu_pastes(self):
        menu = self.entry._entry._translator_edit_menu
        with patch.object(menu, "tk_popup") as popup:
            self.entry._entry.event_generate("<Button-3>", x=10, y=10)
            self.root.update()
            popup.assert_called_once()
        with patch("keyboard_shortcuts.pyperclip.paste", return_value="menu-test-key"):
            menu.invoke(2)
        self.assertEqual(self.entry.get(), "menu-test-key")

    def test_explicit_paste_button(self):
        import customtkinter as ctk
        field = create_key_entry(self.root, "", "Вставити")
        buttons = [w for w in field.master.winfo_children() if isinstance(w, ctk.CTkButton)]
        self.assertEqual(len(buttons), 1)
        with patch("keyboard_shortcuts.pyperclip.paste", return_value="button-test-key"):
            buttons[0].invoke()
        self.assertEqual(field.get(), "button-test-key")

    def test_multiline_paste_replaces_selection_and_readonly_stays_unchanged(self):
        import customtkinter as ctk
        field = ctk.CTkTextbox(self.root)
        field.pack()
        enable_edit_shortcuts(field)
        field.insert("1.0", "replace me")
        field._textbox.tag_add("sel", "1.0", "end-1c")
        with patch("keyboard_shortcuts.pyperclip.paste", return_value="Український\nтекст"):
            field._textbox._translator_edit_menu.invoke(2)
        self.assertEqual(field.get("1.0", "end-1c"), "Український\nтекст")
        field.configure(state="disabled")
        with patch("keyboard_shortcuts.pyperclip.paste", return_value="overwrite"):
            self.assertFalse(paste_text(field._textbox))
        self.assertEqual(field.get("1.0", "end-1c"), "Український\nтекст")


if __name__ == "__main__":
    unittest.main()
