import sys
import os
import json
import time
from datetime import datetime, timedelta
import threading
import ctypes
from ctypes import wintypes
import keyboard
import pyperclip
import pyautogui
import customtkinter as ctk
from pynput import mouse
from google import genai
from anthropic import Anthropic
import win32gui
import win32process

# --- 1. ПРАВА АДМІНІСТРАТОРА ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if not is_admin():
    if getattr(sys, "frozen", False):
        pythonw_executable = sys.executable
        script_arguments = None
    else:
        pythonw_executable = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw_executable):
            pythonw_executable = sys.executable
        script_arguments = f'"{os.path.abspath(__file__)}"'
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", pythonw_executable, script_arguments, None, 1
    )
    sys.exit()

API_KEY = ""
client = None
ANTHROPIC_API_KEY = ""
claude_client = None
CLAUDE_MODEL = "claude-haiku-4-5"
CLAUDE_INPUT_PRICE_PER_MILLION = 1.0
CLAUDE_OUTPUT_PRICE_PER_MILLION = 5.0
gemini_cooldown_until = 0
GEMINI_COOLDOWN_SECONDS = 60

def get_gemini_cooldown_seconds(error_text):
    if "PerDay" in error_text or "RequestsPerDay" in error_text:
        try:
            from zoneinfo import ZoneInfo
            pacific_now = datetime.now(ZoneInfo("America/Los_Angeles"))
            next_reset = (pacific_now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return max(int((next_reset - pacific_now).total_seconds()), 60)
        except Exception:
            return 24 * 60 * 60
    return GEMINI_COOLDOWN_SECONDS

if sys.platform.startswith("win"):
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Translator.App")
    except Exception:
        pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("Перекладач")
app.geometry("380x360")
app.resizable(False, False)
app.attributes("-topmost", True)
try:
    icon_path = os.path.join(
        os.path.dirname(ctk.__file__), "assets", "icons", "CustomTkinter_icon_Windows.ico"
    )
    app.iconbitmap(default=icon_path)
except Exception:
    pass

# --- 2. ГЛОБАЛЬНИЙ СТАН ---
HOTKEY_REPLACE = "ctrl+q"
HOTKEY_POPUP = "ctrl+w"
SETTINGS_FILE = os.path.join(
    os.getenv("APPDATA", os.path.expanduser("~")),
    "translator_settings.json"
)

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
            return settings if isinstance(settings, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

saved_settings = load_settings()
saved_replace_hotkey = saved_settings.get("replace_hotkey", HOTKEY_REPLACE)
saved_popup_hotkey = saved_settings.get("popup_hotkey", HOTKEY_POPUP)
HOTKEY_REPLACE = saved_replace_hotkey if isinstance(saved_replace_hotkey, str) and saved_replace_hotkey.strip() else "ctrl+q"
HOTKEY_POPUP = saved_popup_hotkey if isinstance(saved_popup_hotkey, str) and saved_popup_hotkey.strip() else "ctrl+w"
gemini_enabled = saved_settings.get("gemini_enabled", True) is not False
claude_enabled = saved_settings.get("claude_enabled", True) is not False

UI_LANGUAGES = {
    "uk": "Українська",
    "ru": "Русский",
    "en": "English",
}
UI_TEXT = {
    "uk": {
        "app_title": "Перекладач", "interface_language": "Мова інтерфейсу:",
        "main_language": "Основна мова:", "translate_language": "Мова перекладу:",
        "context": "Контекст розмови (необов'язково):", "status": "Виділіть текст і скористайтеся гарячою клавішею",
        "debug": "Відкрити дебаг", "api_settings": "Налаштування API", "gemini_key": "Ключ Gemini API:",
        "claude_key": "Ключ Claude API:", "save": "Зберегти", "debug_title": "Дебаг перекладача",
        "clear": "Очистити", "close": "Закрити", "choose_action": "Виберіть дію:",
        "translate": "🌐 Перекласти", "replace": "✍️ Замінити текст", "fix": "📝 Виправити помилки",
        "copy": "Копіювати", "loading": "⏳ Завантаження...", "processing": "⏳ Обробка...",
        "no_text": "Текст не знайдено", "api_missing": "Не задано ключ Gemini або Claude API.",
        "gemini_cooldown": "Gemini тимчасово недоступний через ліміт запитів.",
        "replace_hotkey": "Заміна тексту:", "popup_hotkey": "Показ перекладу:",
        "hotkey_hint": "Приклад: ctrl+q або ctrl+shift+t",
        "gemini_enabled": "Використовувати Gemini", "claude_enabled": "Використовувати Claude",
    },
    "ru": {
        "app_title": "Переводчик", "interface_language": "Язык интерфейса:",
        "main_language": "Основной язык:", "translate_language": "Язык перевода:",
        "context": "Контекст разговора (необязательно):", "status": "Выделите текст и используйте горячую клавишу",
        "debug": "Открыть отладку", "api_settings": "Настройки API", "gemini_key": "Ключ Gemini API:",
        "claude_key": "Ключ Claude API:", "save": "Сохранить", "debug_title": "Отладка переводчика",
        "clear": "Очистить", "close": "Закрыть", "choose_action": "Выберите действие:",
        "translate": "🌐 Перевести", "replace": "✍️ Заменить текст", "fix": "📝 Исправить ошибки",
        "copy": "Копировать", "loading": "⏳ Загрузка...", "processing": "⏳ Обработка...",
        "no_text": "Текст не найден", "api_missing": "Не указаны ключи Gemini или Claude API.",
        "gemini_cooldown": "Gemini временно недоступен из-за лимита запросов.",
        "replace_hotkey": "Замена текста:", "popup_hotkey": "Показ перевода:",
        "hotkey_hint": "Пример: ctrl+q или ctrl+shift+t",
        "gemini_enabled": "Использовать Gemini", "claude_enabled": "Использовать Claude",
    },
    "en": {
        "app_title": "Translator", "interface_language": "Interface language:",
        "main_language": "Main language:", "translate_language": "Translation language:",
        "context": "Conversation context (optional):", "status": "Select text and use a hotkey",
        "debug": "Open debug", "api_settings": "API settings", "gemini_key": "Gemini API key:",
        "claude_key": "Claude API key:", "save": "Save", "debug_title": "Translator debug",
        "clear": "Clear", "close": "Close", "choose_action": "Choose an action:",
        "translate": "🌐 Translate", "replace": "✍️ Replace text", "fix": "📝 Fix mistakes",
        "copy": "Copy", "loading": "⏳ Loading...", "processing": "⏳ Processing...",
        "no_text": "Text not found", "api_missing": "Gemini or Claude API key is not set.",
        "gemini_cooldown": "Gemini is temporarily unavailable because of the request limit.",
        "replace_hotkey": "Replace text:", "popup_hotkey": "Show translation:",
        "hotkey_hint": "Example: ctrl+q or ctrl+shift+t",
        "gemini_enabled": "Use Gemini", "claude_enabled": "Use Claude",
    },
}
BASE_LANGUAGE_NAMES = {
    "uk": {"Ukrainian": "Українська", "Russian": "Російська", "English": "Англійська"},
    "ru": {"Ukrainian": "Украинский", "Russian": "Русский", "English": "Английский"},
    "en": {"Ukrainian": "Ukrainian", "Russian": "Russian", "English": "English"},
}
saved_base_language = saved_settings.get("base_language", "Ukrainian")
interface_language = {"Ukrainian": "uk", "Russian": "ru", "English": "en"}.get(
    saved_base_language, "uk"
)

def tr(key):
    return UI_TEXT[interface_language][key]

app.title(tr("app_title"))

def configure_api_clients(gemini_key, claude_key):
    global API_KEY, client, ANTHROPIC_API_KEY, claude_client
    API_KEY = gemini_key.strip()
    ANTHROPIC_API_KEY = claude_key.strip()
    client = genai.Client(api_key=API_KEY) if API_KEY and gemini_enabled else None
    claude_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY and claude_enabled else None

configure_api_clients(
    saved_settings.get("gemini_api_key", os.getenv("GEMINI_API_KEY", "")),
    saved_settings.get("claude_api_key", os.getenv("ANTHROPIC_API_KEY", ""))
)

# --- 3. UI НАЛАШТУВАННЯ ---
title_frame = ctk.CTkFrame(app, fg_color="transparent")
title_frame.pack(fill="x", padx=12, pady=(8, 2))
title_label = ctk.CTkLabel(title_frame, text=tr("app_title"), font=("Arial", 16, "bold"))
title_label.pack(side="left", expand=True)
settings_button = ctk.CTkButton(
    title_frame, text="⚙", width=32, height=28, font=("Arial", 16), command=lambda: show_api_settings()
)
settings_button.pack(side="right")

base_lang_frame = ctk.CTkFrame(app, fg_color="transparent")
base_lang_frame.pack(pady=4)
base_lang_label = ctk.CTkLabel(base_lang_frame, text=tr("main_language"), font=("Arial", 11))
base_lang_label.pack(side="left", padx=5)

base_lang_select = ctk.CTkOptionMenu(
    base_lang_frame, values=list(BASE_LANGUAGE_NAMES[interface_language].values()), width=120
)
base_lang_select.set(
    BASE_LANGUAGE_NAMES[interface_language].get(saved_base_language, BASE_LANGUAGE_NAMES[interface_language]["Ukrainian"])
)
base_lang_select.pack(side="left", padx=5)

target_languages = {
    "EN": "English", "PL": "Polish", "DE": "German", "ES": "Spanish",
    "FR": "French", "IT": "Italian", "NL": "Dutch",
}
TARGET_LANGUAGE_NAMES = {
    "uk": {"English": "Англійська", "Polish": "Польська", "German": "Німецька", "Spanish": "Іспанська", "French": "Французька", "Italian": "Італійська", "Dutch": "Нідерландська"},
    "ru": {"English": "Английский", "Polish": "Польский", "German": "Немецкий", "Spanish": "Испанский", "French": "Французский", "Italian": "Итальянский", "Dutch": "Нидерландский"},
    "en": {"English": "English", "Polish": "Polish", "German": "German", "Spanish": "Spanish", "French": "French", "Italian": "Italian", "Dutch": "Dutch"},
}
saved_target_language = saved_settings.get("target_language", "English")
target_language = (
    saved_target_language if saved_target_language in target_languages else "English"
)
language_buttons = {}

lang_label = ctk.CTkLabel(app, text=tr("translate_language"), font=("Arial", 11))
lang_label.pack(pady=(6, 2))

lang_buttons_frame = ctk.CTkFrame(app, fg_color="transparent")
lang_buttons_frame.pack(pady=(0, 4))

def select_target_language(language):
    global target_language
    target_language = language
    for code, button in language_buttons.items():
        button.configure(
            fg_color="#1f538d" if target_languages[code] == language else "#333333",
            hover_color="#14375e" if target_languages[code] == language else "#444444"
        )
    save_settings()

for index, (code, language) in enumerate(target_languages.items()):
    language_button = ctk.CTkButton(
        lang_buttons_frame,
        text=TARGET_LANGUAGE_NAMES[interface_language][language],
        width=105,
        height=26,
        fg_color="#1f538d" if language == target_language else "#333333",
        hover_color="#14375e" if language == target_language else "#444444",
        command=lambda selected_language=language: select_target_language(selected_language)
    )
    language_button.grid(row=index // 3, column=index % 3, padx=3, pady=3)
    language_buttons[code] = language_button

context_label = ctk.CTkLabel(app, text=tr("context"), font=("Arial", 11))
context_label.pack(pady=(6, 2))

conversation_context_box = ctk.CTkTextbox(app, width=340, height=46, wrap="word")
conversation_context_box.pack(padx=20, pady=(0, 4))
conversation_context_box.insert("1.0", saved_settings.get("context", ""))

def save_settings():
    base_language_display = base_lang_select.get()
    base_language = next(
        (language for language, name in BASE_LANGUAGE_NAMES[interface_language].items()
         if name == base_language_display),
        "Ukrainian"
    )
    settings = {
        "interface_language": interface_language,
        "base_language": base_language,
        "target_language": target_language,
        "context": conversation_context_box.get("1.0", "end-1c"),
        "gemini_api_key": API_KEY,
        "claude_api_key": ANTHROPIC_API_KEY,
        "gemini_enabled": gemini_enabled,
        "claude_enabled": claude_enabled,
        "replace_hotkey": HOTKEY_REPLACE,
        "popup_hotkey": HOTKEY_POPUP,
    }
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as settings_file:
            json.dump(settings, settings_file, ensure_ascii=False, indent=2)
    except OSError:
        pass

def select_base_language(selected_name):
    global interface_language
    selected_language = next(
        (language for language, name in BASE_LANGUAGE_NAMES[interface_language].items()
         if name == selected_name),
        "Ukrainian"
    )
    interface_language = {"Ukrainian": "uk", "Russian": "ru", "English": "en"}[selected_language]
    apply_interface_language(selected_language)
    save_settings()

def get_selected_base_language():
    return next(
        (language for language, name in BASE_LANGUAGE_NAMES[interface_language].items()
         if name == base_lang_select.get()),
        "Ukrainian"
    )

def apply_interface_language(current_base_language=None):
    if current_base_language is None:
        current_base_language = get_selected_base_language()
    app.title(tr("app_title"))
    title_label.configure(text=tr("app_title"))
    base_lang_label.configure(text=tr("main_language"))
    base_lang_select.configure(values=list(BASE_LANGUAGE_NAMES[interface_language].values()))
    base_lang_select.set(BASE_LANGUAGE_NAMES[interface_language].get(current_base_language, BASE_LANGUAGE_NAMES[interface_language]["Ukrainian"]))
    lang_label.configure(text=tr("translate_language"))
    for code, button in language_buttons.items():
        button.configure(text=TARGET_LANGUAGE_NAMES[interface_language][target_languages[code]])
    context_label.configure(text=tr("context"))
    status_lbl.configure(text=tr("status"))
    debug_button.configure(text=tr("debug"))

def show_api_settings():
    api_window = ctk.CTkToplevel(app)
    api_window.title(tr("api_settings"))
    api_window.geometry("390x370")
    api_window.attributes("-topmost", True)

    ctk.CTkLabel(api_window, text=tr("gemini_key"), anchor="w").pack(fill="x", padx=15, pady=(12, 2))
    gemini_entry = ctk.CTkEntry(api_window, width=350, show="*")
    gemini_entry.insert(0, API_KEY)
    gemini_entry.pack(padx=15, pady=(0, 8))

    gemini_enabled_checkbox = ctk.CTkCheckBox(api_window, text=tr("gemini_enabled"))
    gemini_enabled_checkbox.pack(anchor="w", padx=15, pady=(0, 10))
    if gemini_enabled:
        gemini_enabled_checkbox.select()

    ctk.CTkLabel(api_window, text=tr("claude_key"), anchor="w").pack(fill="x", padx=15, pady=(0, 2))
    claude_entry = ctk.CTkEntry(api_window, width=350, show="*")
    claude_entry.insert(0, ANTHROPIC_API_KEY)
    claude_entry.pack(padx=15, pady=(0, 10))

    claude_enabled_checkbox = ctk.CTkCheckBox(api_window, text=tr("claude_enabled"))
    claude_enabled_checkbox.pack(anchor="w", padx=15, pady=(0, 10))
    if claude_enabled:
        claude_enabled_checkbox.select()

    ctk.CTkLabel(api_window, text=tr("replace_hotkey"), anchor="w").pack(fill="x", padx=15, pady=(0, 2))
    replace_hotkey_entry = ctk.CTkEntry(api_window, width=350)
    replace_hotkey_entry.insert(0, HOTKEY_REPLACE)
    replace_hotkey_entry.pack(padx=15, pady=(0, 3))

    ctk.CTkLabel(api_window, text=tr("popup_hotkey"), anchor="w").pack(fill="x", padx=15, pady=(0, 2))
    popup_hotkey_entry = ctk.CTkEntry(api_window, width=350)
    popup_hotkey_entry.insert(0, HOTKEY_POPUP)
    popup_hotkey_entry.pack(padx=15, pady=(0, 2))

    ctk.CTkLabel(api_window, text=tr("hotkey_hint"), text_color="gray", anchor="w").pack(fill="x", padx=15, pady=(0, 10))

    def save_api_settings():
        global HOTKEY_REPLACE, HOTKEY_POPUP, gemini_enabled, claude_enabled
        new_replace_hotkey = replace_hotkey_entry.get().strip()
        new_popup_hotkey = popup_hotkey_entry.get().strip()
        if not new_replace_hotkey or not new_popup_hotkey:
            return
        gemini_enabled = bool(gemini_enabled_checkbox.get())
        claude_enabled = bool(claude_enabled_checkbox.get())
        configure_api_clients(gemini_entry.get(), claude_entry.get())
        HOTKEY_REPLACE = new_replace_hotkey
        HOTKEY_POPUP = new_popup_hotkey
        rebind_shortcuts()
        save_settings()
        destroy_toplevel(api_window)

    ctk.CTkButton(api_window, text=tr("save"), width=110, height=26, command=save_api_settings).pack()
    api_window.protocol("WM_DELETE_WINDOW", lambda: destroy_toplevel(api_window))

base_lang_select.configure(command=select_base_language)
conversation_context_box.bind("<KeyRelease>", lambda _: save_settings())

def close_app():
    save_settings()
    keyboard.unhook_all_hotkeys()
    app.destroy()

app.protocol("WM_DELETE_WINDOW", close_app)

status_lbl = ctk.CTkLabel(app, text=tr("status"), font=("Arial", 10), text_color="gray")
status_lbl.pack(pady=(5, 0))

debug_window = None
debug_box = None
debug_messages = []

def destroy_toplevel(window):
    if window and window.winfo_exists():
        try:
            from customtkinter.windows.widgets.scaling.scaling_tracker import ScalingTracker
            ScalingTracker.window_widgets_dict.pop(window, None)
            ScalingTracker.window_dpi_scaling_dict.pop(window, None)
        except Exception:
            pass
        window.destroy()

def log_debug(message):
    timestamp = time.strftime("%H:%M:%S")
    debug_messages.append(f"[{timestamp}] {message}")

    def append_message():
        if debug_box and debug_box.winfo_exists():
            debug_box.configure(state="normal")
            debug_box.insert("end", f"[{timestamp}] {message}\n")
            debug_box.see("end")
            debug_box.configure(state="disabled")

    app.after(0, append_message)

def show_debug_window():
    global debug_window, debug_box

    if debug_window and debug_window.winfo_exists():
        debug_window.focus_force()
        return

    debug_window = ctk.CTkToplevel(app)
    debug_window.title(tr("debug_title"))
    debug_window.geometry("560x320")
    debug_window.attributes("-topmost", True)

    debug_box = ctk.CTkTextbox(debug_window, width=530, height=250, wrap="word")
    debug_box.pack(padx=10, pady=(10, 5), fill="both", expand=True)
    debug_box.configure(state="disabled")

    controls = ctk.CTkFrame(debug_window, fg_color="transparent")
    controls.pack(pady=(0, 8))

    def clear_debug():
        debug_messages.clear()
        debug_box.configure(state="normal")
        debug_box.delete("1.0", "end")
        debug_box.configure(state="disabled")

    ctk.CTkButton(controls, text=tr("clear"), width=90, height=24, command=clear_debug).pack(side="left", padx=4)
    ctk.CTkButton(controls, text=tr("close"), width=90, height=24, command=lambda: destroy_toplevel(debug_window)).pack(side="left", padx=4)

    if debug_messages:
        debug_box.configure(state="normal")
        debug_box.insert("1.0", "\n".join(debug_messages) + "\n")
        debug_box.see("end")
        debug_box.configure(state="disabled")

debug_button = ctk.CTkButton(app, text=tr("debug"), width=130, height=24, command=show_debug_window)
debug_button.pack(pady=(6, 0))

# --- 4. API & ФУНКЦІЇ ПЕРЕКЛАДУ ---
def normalize_model_result(result: str) -> str:
    lines = [line.strip() for line in result.strip().splitlines() if line.strip()]
    alternative_markers = {"or", "або", "или"}
    for index, line in enumerate(lines):
        if index > 0 and line.lower() in alternative_markers:
            return lines[index - 1]
    return " ".join(lines)


def run_claude_action(prompt: str) -> str:
    log_debug(f"Claude: запит до моделі {CLAUDE_MODEL}")
    try:
        strict_prompt = (
            f"{prompt}\n\n"
            "Output exactly one best answer only. Never provide alternatives, synonyms, "
            "options, explanations, or the word 'or'. Keep the answer on one line."
        )
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": strict_prompt}]
        )
        result = normalize_model_result(response.content[0].text)
        usage = getattr(response, "usage", None)
        if usage:
            input_tokens = getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "output_tokens", 0)
            estimated_cost = (
                input_tokens * CLAUDE_INPUT_PRICE_PER_MILLION
                + output_tokens * CLAUDE_OUTPUT_PRICE_PER_MILLION
            ) / 1_000_000
            log_debug(
                f"Claude: токени: {input_tokens} вхідних + {output_tokens} вихідних = "
                f"{input_tokens + output_tokens}; приблизно ${estimated_cost:.6f}"
            )
        log_debug(f"Claude: отримано відповідь: {result[:120]!r}")
        return result
    except Exception as e:
        error_text = str(e)
        log_debug(f"Claude: помилка: {error_text[:200]}")
        return f"Помилка Claude: {error_text}"

def run_gemini_action(text: str, action_type="translate", target_lang="English", context="") -> str:
    global gemini_cooldown_until

    log_debug(f"API: запит на {action_type}, текст: {text[:120]!r}")
    base_lang = get_selected_base_language()
    context_instruction = (
        f"Conversation context:\n{context}\n"
        "Use this context to choose the correct meaning, terminology, and tone.\n"
        if context else ""
    )

    if action_type == "translate":
        prompt = f"""
        Translate accurately.
        Rules:
        - If input is NOT {base_lang} -> translate to {base_lang}.
        - If input IS {base_lang} -> translate to {target_lang}.
        - Output ONLY translated text without quotes or explanations.

        {context_instruction}
        Text:
        {text}
        """
    elif action_type == "fix":
        prompt = f"""
        Fix grammar, punctuation, and improve phrasing while keeping the original language and tone.
        Return ONLY corrected text without comments.
        
        {context_instruction}
        Text:
        {text}
        """
    else:
        prompt = f"{context_instruction}Translate to {target_lang}:\n{text}"

    if client is None:
        log_debug("API: GEMINI_API_KEY is not set")
        if claude_client:
            log_debug("API: використовую Claude Haiku")
            return run_claude_action(prompt)
        return tr("api_missing")

    if time.time() < gemini_cooldown_until:
        remaining_seconds = int(gemini_cooldown_until - time.time())
        log_debug(f"API: Gemini пропущено, cooldown ще {remaining_seconds} с")
        if claude_client:
            return run_claude_action(prompt)
        return tr("gemini_cooldown")

    try:
        chat = client.chats.create(model="gemini-3.6-flash")
        response = chat.send_message(
            prompt,
            config={"temperature": 0.0, "max_output_tokens": 600}
        )
        result = normalize_model_result(response.text)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_token_count", 0)
            output_tokens = getattr(usage, "candidates_token_count", 0)
            total_tokens = getattr(usage, "total_token_count", prompt_tokens + output_tokens)
            log_debug(
                f"Gemini: токени: {prompt_tokens} вхідних + {output_tokens} вихідних = "
                f"{total_tokens}; приблизно $0.00 у межах free tier"
            )
        log_debug(f"API: отримано відповідь: {result[:120]!r}")
        return result
    except Exception as e:
        error_text = str(e)
        if "429" in error_text or "RESOURCE_EXHAUSTED" in error_text:
            log_debug("API: перевищено квоту (429 RESOURCE_EXHAUSTED)")
            cooldown_seconds = get_gemini_cooldown_seconds(error_text)
            gemini_cooldown_until = time.time() + cooldown_seconds
            log_debug(f"API: Gemini пропущено на {cooldown_seconds // 3600} год.")
            if claude_client:
                log_debug("API: Gemini недоступний, перемикаюся на Claude Haiku")
                return run_claude_action(prompt)
            return (
                "Вичерпано ліміт запитів Gemini. "
                "Додайте ANTHROPIC_API_KEY для автоматичного переходу на Claude."
            )
        log_debug(f"API: помилка: {error_text[:200]}")
        return f"Помилка Gemini: {error_text}"

def grab_selected_text_direct() -> str:
    time.sleep(0.2)
    pyautogui.keyUp('ctrl')
    pyautogui.keyUp('shift')
    pyautogui.keyUp('alt')
    time.sleep(0.03)

    clipboard_marker = f"__translator_copy_{time.time_ns()}__"
    pyperclip.copy(clipboard_marker)
    pyautogui.hotkey('ctrl', 'c')

    for _ in range(12):
        time.sleep(0.05)
        text = pyperclip.paste()
        if text != clipboard_marker:
            selected_text = text.strip()
            log_debug(f"Буфер: отримано {len(selected_text)} символів")
            return selected_text

    log_debug("Буфер: Ctrl+C не змінив буфер обміну")
    return ""

# --- 5. МЕНЕДЖЕР КУЛЬКИ ТА МЕНЮ ---
class AssistantBubble:
    def __init__(self, master):
        self.master = master
        self.bubble = None
        self.action_menu = None
        self.result_popup = None
        self.cached_text = ""
        self.last_target_hwnd = None

    def show_bubble(self, x, y, selected_text, target_hwnd):
        self.cached_text = selected_text
        self.last_target_hwnd = target_hwnd

        if self.bubble and self.bubble.winfo_exists():
            self.bubble.geometry(f"32x32+{x+12}+{y-18}")
            return

        self.bubble = ctk.CTkToplevel(self.master)
        self.bubble.overrideredirect(True)
        self.bubble.attributes("-topmost", True)
        self.bubble.geometry(f"32x32+{x+12}+{y-18}")

        btn = ctk.CTkButton(
            self.bubble, 
            text="✦", 
            font=("Arial", 15, "bold"),
            width=32, 
            height=32, 
            corner_radius=16,
            fg_color="#1f538d",
            hover_color="#14375e",
            command=self.open_action_menu
        )
        btn.pack(fill="both", expand=True)

    def hide_bubble(self):
        if self.bubble and self.bubble.winfo_exists():
            destroy_toplevel(self.bubble)

    def open_action_menu(self):
        x, y = pyautogui.position()
        self.hide_bubble()

        if self.action_menu and self.action_menu.winfo_exists():
            destroy_toplevel(self.action_menu)

        self.action_menu = ctk.CTkToplevel(self.master)
        self.action_menu.overrideredirect(True)
        self.action_menu.attributes("-topmost", True)
        self.action_menu.geometry(f"190x150+{x}+{y}")

        ctk.CTkLabel(self.action_menu, text=tr("choose_action"), font=("Arial", 11, "bold")).pack(pady=(6, 4))

        ctk.CTkButton(
            self.action_menu, text=tr("translate"), height=24, font=("Arial", 11),
            command=lambda: self._handle_menu_choice("translate", "popup")
        ).pack(pady=2, padx=10, fill="x")

        ctk.CTkButton(
            self.action_menu, text=tr("replace"), height=24, font=("Arial", 11),
            command=lambda: self._handle_menu_choice("translate", "replace")
        ).pack(pady=2, padx=10, fill="x")

        ctk.CTkButton(
            self.action_menu, text=tr("fix"), height=24, font=("Arial", 11),
            command=lambda: self._handle_menu_choice("fix", "popup")
        ).pack(pady=2, padx=10, fill="x")

        self.master.after(300, lambda: self._bind_autoclose(self.action_menu))

    def _handle_menu_choice(self, action_type, display_mode):
        text_to_process = self.cached_text
        target_hwnd = self.last_target_hwnd
        if self.action_menu and self.action_menu.winfo_exists():
            destroy_toplevel(self.action_menu)

        if display_mode == "popup":
            self.execute_popup_action(action_type, text_to_process)
        elif display_mode == "replace":
            self.execute_replace_action(action_type, text_to_process, target_hwnd)

    def show_result_popup(self, text=None):
        if text is None:
            text = tr("loading")
        if self.result_popup and self.result_popup.winfo_exists():
            destroy_toplevel(self.result_popup)

        self.result_popup = ctk.CTkToplevel(self.master)
        self.result_popup.overrideredirect(True)
        self.result_popup.attributes("-topmost", True)

        x, y = pyautogui.position()
        popup_height, text_height = self._result_popup_dimensions(text)
        self.result_popup.geometry(f"340x{popup_height}+{x+10}+{y+10}")

        self.res_box = ctk.CTkTextbox(
            self.result_popup, width=320, height=text_height, font=("Arial", 12), wrap="word"
        )
        self.res_box.insert("1.0", text)
        self.res_box.pack(pady=(8, 4), padx=10)

        buttons_frame = ctk.CTkFrame(self.result_popup, fg_color="transparent")
        buttons_frame.pack(pady=(0, 6))

        ctk.CTkButton(
            buttons_frame, text=tr("copy"), width=95, height=22,
            command=self.copy_result
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            buttons_frame, text=tr("close"), width=70, height=22,
            fg_color="#D32F2F", hover_color="#B71C1C", command=lambda: destroy_toplevel(self.result_popup)
        ).pack(side="left", padx=4)

        self.master.after(300, lambda: self._bind_autoclose(self.result_popup))

    def _result_popup_dimensions(self, text):
        estimated_lines = sum(
            max(1, (len(line) + 47) // 48)
            for line in text.splitlines()
        ) or 1
        text_height = min(610, max(80, estimated_lines * 20 + 10))
        return min(700, text_height + 90), text_height

    def _bind_autoclose(self, win):
        if win and win.winfo_exists():
            win.focus_force()

            def close_when_focus_leaves(event):
                focused_widget = self.master.focus_get()
                if focused_widget is None or focused_widget.winfo_toplevel() != win:
                    destroy_toplevel(win)

            win.bind("<FocusOut>", close_when_focus_leaves)

    def copy_result(self):
        if self.result_popup and self.result_popup.winfo_exists():
            pyperclip.copy(self.res_box.get("1.0", "end-1c"))

    def update_result_text(self, text):
        if self.result_popup and self.result_popup.winfo_exists():
            self.res_box.configure(state="normal")
            self.res_box.delete("1.0", "end")
            self.res_box.insert("1.0", text)
            popup_height, text_height = self._result_popup_dimensions(text)
            self.res_box.configure(height=text_height)
            self.result_popup.geometry(
                f"340x{popup_height}+{self.result_popup.winfo_x()}+{self.result_popup.winfo_y()}"
            )

    def execute_popup_action(self, action_type="translate", text=None):
        raw_text = text or grab_selected_text_direct()
        if not raw_text:
            log_debug(tr("no_text"))
            return

        log_debug("Вікно перекладу: команда запущена")
        context = conversation_context_box.get("1.0", "end-1c").strip()
        
        self.show_result_popup(tr("processing"))
        def worker():
            target = target_language
            res = run_gemini_action(raw_text, action_type, target, context)
            pyperclip.copy(res)
            log_debug("Вікно перекладу: результат скопійовано в буфер")
            self.master.after(0, lambda: self.update_result_text(res))
        threading.Thread(target=worker, daemon=True).start()

    def execute_replace_action(self, action_type="translate", text=None, target_hwnd=None):
        raw_text = text or grab_selected_text_direct()
        if not raw_text:
            log_debug(tr("no_text"))
            return

        log_debug("Заміна: команда Ctrl+Q спрацювала")
        context = conversation_context_box.get("1.0", "end-1c").strip()

        def worker():
            target = target_language
            res = run_gemini_action(raw_text, action_type, target, context)
            pyperclip.copy(res)
            
            # Повертаємо фокус у вікно, де був текст, перед вставкою
            if target_hwnd:
                try:
                    win32gui.SetForegroundWindow(target_hwnd)
                except:
                    pass
            time.sleep(0.08)
            pyautogui.hotkey('ctrl', 'v')
            log_debug("Заміна: результат вставлено")

        threading.Thread(target=worker, daemon=True).start()

bubble_manager = AssistantBubble(app)

# --- 6. РЕЄСТРАЦІЯ ШОРТКАТІВ ---
def rebind_shortcuts():
    try:
        keyboard.unhook_all_hotkeys()
    except:
        pass

    try:
        keyboard.add_hotkey(
            HOTKEY_REPLACE,
            lambda: bubble_manager.execute_replace_action("translate"),
            suppress=True,
            trigger_on_release=True
        )
        keyboard.add_hotkey(
            HOTKEY_POPUP,
            lambda: bubble_manager.execute_popup_action("translate"),
            suppress=True,
            trigger_on_release=True
        )
    except Exception as e:
        log_debug(f"Hotkeys: помилка реєстрації: {e}")

rebind_shortcuts()

app.mainloop()