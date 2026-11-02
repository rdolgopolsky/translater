"""Local TranslateGemma requests, language detection and failure backoff."""
import json
import threading
import time
import urllib.request

from lingua import Language, LanguageDetectorBuilder

MODEL = "translategemma:4b"
BASE_URL = "http://127.0.0.1:11434"
LANGUAGES = {
    "English": ("en", Language.ENGLISH), "Polish": ("pl", Language.POLISH),
    "German": ("de", Language.GERMAN), "Spanish": ("es", Language.SPANISH),
    "French": ("fr", Language.FRENCH), "Italian": ("it", Language.ITALIAN),
    "Dutch": ("nl", Language.DUTCH), "Japanese": ("ja", Language.JAPANESE),
    "Korean": ("ko", Language.KOREAN), "Chinese": ("zh-Hans", Language.CHINESE),
    "Portuguese": ("pt", Language.PORTUGUESE), "Turkish": ("tr", Language.TURKISH),
    "Czech": ("cs", Language.CZECH), "Arabic": ("ar", Language.ARABIC),
    "Swedish": ("sv", Language.SWEDISH), "Danish": ("da", Language.DANISH),
    "Finnish": ("fi", Language.FINNISH), "Ukrainian": ("uk", Language.UKRAINIAN),
    "Russian": ("ru", Language.RUSSIAN),
}


class OllamaUnavailable(RuntimeError):
    pass


class OllamaTranslator:
    def __init__(self, base_url=BASE_URL, timeout=25, retry_after=60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retry_after = retry_after
        self._retry_at = 0
        self._stop = threading.Event()
        self._thread = None
        self._detector = None
        self._loaded = False

    @property
    def in_cooldown(self):
        return time.monotonic() < self._retry_at

    def _post(self, endpoint, payload, timeout=None):
        request = urllib.request.Request(
            self.base_url + endpoint, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        # Loopback traffic should not be sent through a configured web proxy.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=timeout or self.timeout) as response:
            body = response.read(1_048_577)
        if len(body) > 1_048_576:
            raise OllamaUnavailable("Ollama response is too large")
        result = json.loads(body)
        if not isinstance(result, dict) or result.get("error"):
            raise OllamaUnavailable("Ollama returned an error")
        return result

    def detect_source_language(self, text):
        if not text or not text.strip():
            return None
        if self._detector is None:
            self._detector = LanguageDetectorBuilder.from_languages(
                *(language for _, language in LANGUAGES.values())
            ).build()
        detected = self._detector.detect_language_of(text)
        if detected is None:
            return None
        return next((name for name, (_, language) in LANGUAGES.items() if language == detected), None)

    def translate(self, text, base_language, target_language, context=""):
        if self.in_cooldown:
            raise OllamaUnavailable("Ollama is temporarily unavailable; using the backup")
        try:
            if not text.strip() or len(text) > 6000:
                raise OllamaUnavailable("Text exceeds the local translation limit or is empty")
            source = self.detect_source_language(text)
            if source is None:
                raise OllamaUnavailable("Could not determine the source language")
            target = target_language if source == base_language else base_language
            source_code = LANGUAGES[source][0]
            target_code = LANGUAGES[target][0]
            if source == target:
                return text, source_code
            context_block = (
                f"Conversation context (use it to choose the right meaning and tone, do not translate it):\n{context.strip()}\n\n"
                if context and context.strip() else ""
            )
            prompt = (
                f"You are a professional {source} ({source_code}) to {target} ({target_code}) translator. "
                f"Your goal is to accurately convey the meaning and nuances of the original {source} text "
                f"while adhering to {target} grammar, vocabulary, and cultural sensitivities.\n"
                f"{context_block}"
                f"Produce only the {target} translation, without any additional explanations or commentary. "
                f"Please translate the following {source} text into {target}:\n\n\n{text}"
            )
            result = self._post("/api/chat", {
                "model": MODEL, "messages": [{"role": "user", "content": prompt}],
                "stream": False, "keep_alive": "10m",
                "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 2048},
            })
            message = result.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if (result.get("done") is not True or result.get("done_reason") == "length"
                    or not isinstance(content, str) or not content.strip()):
                raise OllamaUnavailable("Ollama returned an empty or incomplete translation")
            self._loaded = True
            self._retry_at = 0
            return content.strip(), source_code
        except Exception:
            self._retry_at = time.monotonic() + self.retry_after
            raise

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = threading.Event()
        stop = self._stop

        def maintain():
            while not stop.is_set():
                try:
                    result = self._post("/api/generate", {
                        "model": MODEL, "keep_alive": "10m", "stream": False,
                        "options": {"num_ctx": 8192},
                    })
                    self._loaded = result.get("done") is True
                except Exception:
                    pass  # A failed preload must never prevent the app from opening.
                if stop.wait(240):
                    break

        self._thread = threading.Thread(target=maintain, daemon=True, name="Ollama-preload")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._loaded:
            try:
                self._post("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=2)
            except Exception:
                pass  # The finite keep_alive also releases memory after a crash.
        self._loaded = False
