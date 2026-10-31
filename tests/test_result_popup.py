"""Exercise the actual popup methods without launching clients or global hotkeys."""
import ast
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest


@unittest.skipUnless(sys.platform == "win32", "Windows popup geometry regression")
class ResultPopupTests(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        import win32api
        import win32con
        import win32gui
        from keyboard_shortcuts import enable_edit_shortcuts
        self.ctk = ctk
        source = ast.parse((Path(__file__).resolve().parents[1] / "translator.py").read_text(encoding="utf-8-sig"))
        nodes = [node for node in source.body if getattr(node, "name", "") in ("AssistantBubble", "destroy_toplevel")]
        namespace = dict(ctk=ctk, win32api=win32api, win32con=win32con, win32gui=win32gui,
                         threading=threading, translation_font_size=14, tr=lambda key: key,
                         enable_edit_shortcuts=enable_edit_shortcuts,
                         pyautogui=SimpleNamespace(position=lambda: (150, 150)))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "translator.py", "exec"), namespace)
        self.root = ctk.CTk()
        self.root.attributes("-topmost", True)
        self.manager = namespace["AssistantBubble"](self.root)
        self.manager._bind_autoclose = lambda window: None

    def tearDown(self):
        self.ctk.set_window_scaling(1.0)
        for job in self.root.tk.call("after", "info"):
            self.root.tk.call("after", "cancel", job)
        self.root.destroy()

    def test_repeated_drag_keeps_window_size_at_different_scalings(self):
        for scale in (1.0, 1.25, 1.5, 2.0):
            with self.subTest(scale=scale):
                self.ctk.set_window_scaling(scale)
                self.manager.show_result_popup("A short translation", "Test")
                self.root.update()
                popup = self.manager.result_popup
                original_size = (popup.winfo_width(), popup.winfo_height())
                original_position = (popup.winfo_x(), popup.winfo_y())
                self.manager._start_popup_drag(SimpleNamespace(x_root=200, y_root=200))
                for offset in range(1, 21):
                    self.manager._drag_popup(SimpleNamespace(x_root=200 + offset, y_root=200 + offset))
                    self.root.update()
                    self.assertEqual((popup.winfo_width(), popup.winfo_height()), original_size)
                self.assertNotEqual((popup.winfo_x(), popup.winfo_y()), original_position)
                self.manager._stop_popup_drag()
                stopped_position = (popup.winfo_x(), popup.winfo_y())
                self.manager._drag_popup(SimpleNamespace(x_root=500, y_root=500))
                self.root.update()
                self.assertEqual((popup.winfo_x(), popup.winfo_y()), stopped_position)

    def test_popup_has_native_close_controls_and_escape(self):
        import win32con
        import win32gui
        self.manager.show_result_popup("Translation", "Test")
        self.root.update()
        popup = self.manager.result_popup
        self.assertFalse(popup.overrideredirect())
        self.assertEqual(tuple(map(int, popup.resizable())), (0, 0))
        hwnd = win32gui.GetParent(popup.winfo_id())
        self.assertFalse(win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOPMOST)
        popup.focus_force()
        self.root.update()
        popup.event_generate("<Escape>")
        self.root.update()
        self.assertFalse(popup.winfo_exists())
        self.assertIsNone(self.manager.result_popup)


if __name__ == "__main__":
    unittest.main()
