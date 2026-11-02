import ast
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import Mock, patch

from ollama_translation import LANGUAGES, MODEL, OllamaTranslator, OllamaUnavailable


class LocalTranslationTests(unittest.TestCase):
    def setUp(self):
        self.service = OllamaTranslator()

    def test_language_coverage_matches_application(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "translator.py").read_text(encoding="utf-8-sig"))
        languages = next(ast.literal_eval(node.value) for node in tree.body
                         if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "target_languages" for t in node.targets))
        self.assertEqual(set(languages.values()), set(LANGUAGES))

    def test_direction_and_translation_prompt(self):
        self.service._post = Mock(return_value={"done": True, "message": {"content": "translated"}})
        cases = [
            ("Привіт! Як справи?", "uk", "English (en)"),
            ("Hello! How are you doing today?", "en", "Ukrainian (uk)"),
            ("こんにちは、お元気ですか？", "ja", "Ukrainian (uk)"),
            ("Привет! Как у тебя дела сегодня?", "ru", "Ukrainian (uk)"),
        ]
        for text, source, destination in cases:
            with self.subTest(source=source):
                result, detected = self.service.translate(text, "Ukrainian", "English")
                self.assertEqual((result, detected), ("translated", source))
                endpoint, payload = self.service._post.call_args.args
                self.assertEqual(endpoint, "/api/chat")
                self.assertEqual(payload["model"], MODEL)
                self.assertIn("to " + destination, payload["messages"][0]["content"])
                self.assertTrue(payload["messages"][0]["content"].endswith("\n\n\n" + text))

    def test_bad_responses_trigger_cooldown(self):
        for response in ({}, {"done": True, "message": {"content": ""}},
                         {"done": False, "message": {"content": "partial"}},
                         {"done": True, "done_reason": "length", "message": {"content": "cut off"}}):
            with self.subTest(response=response):
                service = OllamaTranslator()
                service._post = Mock(return_value=response)
                with self.assertRaises(OllamaUnavailable):
                    service.translate("Hello, how are you today?", "Ukrainian", "English")
                self.assertTrue(service.in_cooldown)
                with self.assertRaises(OllamaUnavailable):
                    service.translate("Hello again", "Ukrainian", "English")
                self.assertEqual(service._post.call_count, 1)

    def test_timeout_and_recovery(self):
        self.service._post = Mock(side_effect=TimeoutError("test"))
        with self.assertRaises(TimeoutError):
            self.service.translate("Hello, how are you?", "Ukrainian", "English")
        self.service._retry_at = 0
        self.service._post = Mock(return_value={"done": True, "message": {"content": "Привіт"}})
        self.assertEqual(self.service.translate("Hello, how are you?", "Ukrainian", "English")[0], "Привіт")
        self.assertFalse(self.service.in_cooldown)

    def test_http_timeout_is_bounded(self):
        import http.server
        import threading

        class SlowHandler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                time.sleep(0.25)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
        thread.start()
        try:
            service = OllamaTranslator(base_url=f"http://127.0.0.1:{server.server_port}", timeout=0.05)
            with self.assertRaises(TimeoutError):
                service._post("/api/chat", {})
        finally:
            server.shutdown()
            server.server_close()

    def test_stop_releases_loaded_model(self):
        self.service._loaded = True
        self.service._post = Mock()
        self.service.stop()
        self.service._post.assert_called_once_with("/api/generate", {"model": MODEL, "keep_alive": 0}, timeout=2)


class ProviderFallbackTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "translator.py").read_text(encoding="utf-8-sig"))
        node = next(node for node in tree.body if getattr(node, "name", "") == "run_gemini_action")
        self.local = Mock()
        self.deepl = Mock(return_value="DeepL translation")
        self.namespace = dict(
            ollama_enabled=True, ollama_service=self.local, OLLAMA_MODEL=MODEL,
            deepl_enabled=True, DEEPL_API_KEY="synthetic-key", run_deepl_action=self.deepl,
            get_selected_base_language=lambda: "Ukrainian", set_active_provider=Mock(),
            log_debug=Mock(), debug_text=lambda key, **kwargs: key, tr=lambda key: key,
            looks_like_translation_instructions=lambda text: text == "BAD INSTRUCTIONS",
            client=None, claude_client=None, gemini_enabled=False,
            gemini_cooldown_until=0, time=time, run_fallback_action=lambda *args: None,
        )
        exec(compile(ast.Module(body=[node], type_ignores=[]), "translator.py", "exec"), self.namespace)
        self.translate = self.namespace["run_gemini_action"]

    def test_local_success_does_not_send_text_to_deepl(self):
        self.local.translate.return_value = ("Local translation", "uk")
        self.assertEqual(self.translate("test"), "Local translation")
        self.deepl.assert_not_called()

    def test_every_local_failure_goes_to_deepl(self):
        for failure in (ConnectionRefusedError(), TimeoutError(), ValueError(), RuntimeError()):
            with self.subTest(failure=type(failure).__name__):
                self.local.translate.side_effect = failure
                self.assertEqual(self.translate("original text"), "DeepL translation")
                self.deepl.assert_called_with("original text", "English")

    def test_instructions_are_not_used_as_translation(self):
        self.local.translate.return_value = ("BAD INSTRUCTIONS", "uk")
        self.assertEqual(self.translate("text"), "DeepL translation")

    def test_disabled_local_provider_goes_directly_to_deepl(self):
        self.namespace["ollama_enabled"] = False
        self.assertEqual(self.translate("text"), "DeepL translation")
        self.local.translate.assert_not_called()

    def test_no_working_provider_returns_error_instead_of_crashing(self):
        self.local.translate.side_effect = ConnectionRefusedError()
        self.deepl.side_effect = TimeoutError()
        self.assertEqual(self.translate("text"), "api_missing")

    def test_fix_action_does_not_use_translation_only_services(self):
        self.assertEqual(self.translate("text", action_type="fix"), "fix_api_missing")
        self.local.translate.assert_not_called()
        self.deepl.assert_not_called()


if __name__ == "__main__":
    unittest.main()
