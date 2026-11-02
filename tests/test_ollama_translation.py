import ast
import collections
import json
from pathlib import Path
import threading
import time
import unittest
import urllib.parse
import urllib.request
from unittest.mock import MagicMock, Mock, patch

from ollama_translation import LANGUAGES, MODEL, OllamaTranslator, OllamaUnavailable
from translator_i18n import MODEL_PRICES, MODEL_RATES


class LocalTranslationTests(unittest.TestCase):
    def setUp(self):
        self.service = OllamaTranslator()

    def test_language_coverage_matches_application(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "translator.py").read_text(encoding="utf-8-sig"))
        languages = next(ast.literal_eval(node.value) for node in tree.body
                         if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "target_languages" for t in node.targets))
        self.assertEqual(set(languages.values()), set(LANGUAGES))

    def test_gemini_allowed_models_have_known_prices_and_rates(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "translator.py").read_text(encoding="utf-8-sig"))
        allowed_models = next(
            ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GEMINI_ALLOWED_MODELS" for t in node.targets)
        )
        for model in allowed_models:
            self.assertIn(model, MODEL_PRICES)
            self.assertIn(model, MODEL_RATES)

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

    def test_context_is_included_in_local_translation_prompt(self):
        self.service._post = Mock(return_value={"done": True, "message": {"content": "translated"}})
        self.service.translate("Привіт! Як справи?", "Ukrainian", "English", context="Formal business email")
        _, payload = self.service._post.call_args.args
        self.assertIn("Formal business email", payload["messages"][0]["content"])

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
        wanted = {"run_gemini_action", "run_deepl_action", "run_cached_action", "_is_error_response"}
        nodes = [node for node in tree.body if getattr(node, "name", "") in wanted]
        self.local = Mock()
        self.deepl = Mock(return_value="DeepL translation")
        self.namespace = dict(
            ollama_enabled=True, ollama_service=self.local, OLLAMA_MODEL=MODEL,
            deepl_enabled=True, DEEPL_API_KEY="synthetic-key", DEEPL_API_URL="https://api-free.deepl.com/v2/translate",
            run_deepl_action=self.deepl, record_deepl_usage=Mock(),
            get_selected_base_language=lambda: "Ukrainian", set_active_provider=Mock(),
            log_debug=Mock(), debug_text=lambda key, **kwargs: key, tr=lambda key: key,
            looks_like_translation_instructions=lambda text: text == "BAD INSTRUCTIONS",
            client=None, claude_client=None, gemini_enabled=False,
            gemini_cooldown_until=0, time=time, run_fallback_action=lambda *args: None,
            cache_lock=threading.Lock(), TRANSLATION_CACHE=collections.OrderedDict(), MAX_CACHE_ENTRIES=64,
            urllib=urllib, json=json,
        )
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "translator.py", "exec"), self.namespace)
        self.raw_deepl = self.namespace["run_deepl_action"]
        self.namespace["run_deepl_action"] = self.deepl
        self.translate = self.namespace["run_gemini_action"]
        self.cached_translate = self.namespace["run_cached_action"]

    def test_local_success_does_not_send_text_to_deepl(self):
        self.local.translate.return_value = ("Local translation", "uk")
        self.assertEqual(self.translate("test"), "Local translation")
        self.deepl.assert_not_called()

    def test_local_receives_context_when_provided(self):
        self.local.translate.return_value = ("Local translation with context", "uk")
        self.assertEqual(self.translate("test", context="software engineering"), "Local translation with context")
        self.local.translate.assert_called_once_with("test", "Ukrainian", "English", "software engineering")

    def test_every_local_failure_goes_to_deepl(self):
        for failure in (ConnectionRefusedError(), TimeoutError(), ValueError(), RuntimeError()):
            with self.subTest(failure=type(failure).__name__):
                self.local.translate.side_effect = failure
                self.assertEqual(self.translate("original text"), "DeepL translation")
                self.deepl.assert_called_with("original text", "English")

    def test_deepl_single_request_when_local_detector_identifies_base_language(self):
        self.local.detect_source_language.return_value = "Ukrainian"
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps({
            "translations": [{"detected_source_language": "UK", "text": "Hello world"}]
        }).encode("utf-8")
        with patch("urllib.request.urlopen", return_value=mock_response) as urlopen_mock:
            result = self.raw_deepl("Привіт світе", "English")
            self.assertEqual(result, "Hello world")
            self.assertEqual(urlopen_mock.call_count, 1)
            req = urlopen_mock.call_args.args[0]
            self.assertIn(b"target_lang=EN", req.data)

    def test_cached_action_returns_cached_result_without_repeating_request(self):
        self.local.translate.return_value = ("Cached translation", "uk")
        first = self.cached_translate("Hello", "translate", "English", "")
        second = self.cached_translate("Hello", "translate", "English", "")
        self.assertEqual(first, "Cached translation")
        self.assertEqual(second, "Cached translation")
        self.assertEqual(self.local.translate.call_count, 1)

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
