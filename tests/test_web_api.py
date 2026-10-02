import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import google.generativeai as genai
    from fastapi.testclient import TestClient
    from web.backend.cloud_agent import CloudAgent, CloudAgentError
    from web.backend.main import app
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None
    app = None


class WebApiTests(unittest.TestCase):
    def setUp(self):
        if not FASTAPI_AVAILABLE:
            self.skipTest("fastapi not installed")
        self.env = patch.dict(os.environ, {
            "WEB_DEMO_USERNAME": "judge",
            "WEB_DEMO_PASSWORD": "unique-test-password",
            "WEB_SESSION_SECRET": "test-only-session-secret-at-least-32-chars",
            "GEMINI_API_KEY": "test-only-key",
            "GROQ_API_KEY": "",
            "WEB_PUBLIC_DEMO": "false",
        })
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        if hasattr(self, 'client') and self.client:
            self.client.close()
        if hasattr(self, 'env') and self.env:
            self.env.stop()

    def test_status_lists_web_and_desktop_capabilities_without_secrets(self):
        with patch("web.backend.main.cloud_agent.groq_api_key", ""):
            response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["web_login_configured"])
        self.assertTrue(body["gemini_configured"])
        self.assertTrue(body["ai_configured"])
        self.assertFalse(body["groq_configured"])
        self.assertFalse(body["authenticated"])
        self.assertFalse(body["public_demo"])
        self.assertEqual(body["status"], "available")
        self.assertIn("camera and gesture control", body["desktop_only"])
        self.assertNotIn("test-only-key", response.text)

    def test_status_reports_groq_only_as_an_available_web_ai_provider(self):
        with (
            patch("web.backend.main.cloud_agent.api_key", ""),
            patch("web.backend.main.cloud_agent.groq_api_key", "test-groq-key"),
        ):
            response = self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ai_configured"])
        self.assertFalse(body["gemini_configured"])
        self.assertTrue(body["groq_configured"])
        self.assertEqual(body["status"], "available")
        self.assertNotIn("test-groq-key", response.text)

    def test_backend_does_not_import_desktop_modules(self):
        imported_desktop_modules = [
            name for name in sys.modules
            if name.startswith(("intent_platform.core", "intent_platform.ui"))
        ]
        self.assertEqual(imported_desktop_modules, [])

    def test_login_issues_httponly_session_and_bad_password_fails(self):
        failed = self.client.post("/api/login", json={"username": "judge", "password": "wrong"})
        self.assertEqual(failed.status_code, 401)

        response = self.client.post("/api/login", json={
            "username": "judge",
            "password": "unique-test-password",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertTrue(self.client.cookies.get("intent_os_session"))
        self.assertIn("httponly", response.headers["set-cookie"].lower())

    def test_login_fails_closed_when_demo_account_is_not_configured(self):
        with patch.dict(os.environ, {
            "WEB_DEMO_USERNAME": "",
            "WEB_DEMO_PASSWORD": "",
            "WEB_SESSION_SECRET": "",
        }):
            response = self.client.post("/api/login", json={
                "username": "judge",
                "password": "anything",
            })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["code"], "login_not_configured")

    def test_chat_requires_login_and_uses_text_only_cloud_agent(self):
        denied = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(denied.status_code, 401)
        self.client.post("/api/login", json={"username": "judge", "password": "unique-test-password"})

        with patch("web.backend.main.cloud_agent.reply", return_value="Hello from the web agent.") as reply:
            response = self.client.post("/api/chat", json={
                "message": "hello",
                "history": [{"role": "user", "content": "previous question"}],
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Hello from the web agent.")
        self.assertFalse(response.json()["desktop_action_taken"])
        reply.assert_called_once()

    def test_public_demo_status_chat_and_agent_need_no_login(self):
        with patch.dict(os.environ, {"WEB_PUBLIC_DEMO": "true"}):
            status_response = self.client.get("/api/status")
            self.assertEqual(status_response.status_code, 200)
            self.assertTrue(status_response.json()["public_demo"])
            self.assertTrue(status_response.json()["authenticated"])

            with patch("web.backend.main.cloud_agent.reply", return_value="Public demo chat works.") as reply:
                chat_response = self.client.post("/api/chat", json={"message": "hello"})
            agent_response = self.client.post("/api/agent", json={"action": "status"})
            logout_response = self.client.post("/api/logout")
            status_after_logout = self.client.get("/api/status")

        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(chat_response.json()["reply"], "Public demo chat works.")
        self.assertFalse(chat_response.json()["desktop_action_taken"])
        self.assertEqual(agent_response.status_code, 200)
        self.assertFalse(agent_response.json()["desktop_action_taken"])
        self.assertEqual(logout_response.status_code, 200)
        self.assertTrue(status_after_logout.json()["authenticated"])
        self.assertNotIn("test-only-key", status_response.text + chat_response.text + agent_response.text)
        reply.assert_called_once()

    def test_public_demo_chat_still_sanitizes_gemini_failures(self):
        with patch.dict(os.environ, {"WEB_PUBLIC_DEMO": "true"}):
            with patch(
                "web.backend.main.cloud_agent.reply",
                side_effect=CloudAgentError("Gemini quota is currently exhausted. Check the API project's plan and limits, then try again."),
            ):
                response = self.client.post("/api/chat", json={"message": "hello"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("quota is currently exhausted", response.json()["detail"]["message"])
        self.assertNotIn("test-only-key", response.text)

    def test_public_demo_requires_exact_true_and_default_auth_remains(self):
        for setting in ("", "1", "yes", "false"):
            with patch.dict(os.environ, {"WEB_PUBLIC_DEMO": setting}):
                response = self.client.post("/api/agent", json={"action": "status"})
            self.assertEqual(response.status_code, 401, setting)

    def test_chat_missing_gemini_key_returns_safe_setup_error(self):
        self.client.post("/api/login", json={"username": "judge", "password": "unique-test-password"})
        with (
            patch("web.backend.main.cloud_agent.api_key", ""),
            patch("web.backend.main.cloud_agent.groq_api_key", ""),
        ):
            response = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("GROQ_API_KEY", response.json()["detail"]["message"])
        self.assertNotIn("test-only-key", response.text)

    def test_chat_returns_safe_quota_message(self):
        self.client.post("/api/login", json={"username": "judge", "password": "unique-test-password"})
        with patch(
            "web.backend.main.cloud_agent.reply",
            side_effect=CloudAgentError("Gemini quota is currently exhausted. Check the API project's plan and limits, then try again."),
        ):
            response = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("quota is currently exhausted", response.json()["detail"]["message"])
        self.assertNotIn("test-only-key", response.text)

    def test_cloud_agent_sanitizes_raw_provider_errors(self):
        class ProviderFailure(Exception):
            pass

        class FakeChat:
            def send_message(self, _message):
                raise ProviderFailure("private provider detail test-only-key")

        agent = CloudAgent()
        agent.api_key = "test-only-key"
        agent.model_name = "gemini-3.8-flash"
        with (
            patch.object(genai, "configure"),
            patch.object(genai, "GenerativeModel") as model_factory,
        ):
            model_factory.return_value.start_chat.return_value = FakeChat()
            with self.assertRaises(CloudAgentError) as error:
                agent.reply("hello", [])

        self.assertNotIn("private provider detail", str(error.exception))
        self.assertNotIn("test-only-key", str(error.exception))

    def test_cloud_agent_sends_project_context_to_gemini(self):
        class FakeChat:
            def send_message(self, message):
                self.message = message
                return type("FakeResponse", (), {"text": "Gemini-generated project explanation."})()

        agent = CloudAgent()
        agent.api_key = "test-only-key"
        agent.model_name = "gemini-2.5-flash"
        with (
            patch.object(genai, "configure"),
            patch.object(genai, "GenerativeModel") as model_factory,
        ):
            fake_chat = FakeChat()
            model_factory.return_value.start_chat.return_value = fake_chat
            answer = agent.reply("What is Intent OS?", [])

        self.assertEqual(answer, "Gemini-generated project explanation.")
        self.assertIn("UNDERSTAND → OBSERVE → DECIDE → EXECUTE → VERIFY", model_factory.call_args.kwargs["system_instruction"])
        self.assertIn("AI interview assistance", model_factory.call_args.kwargs["system_instruction"])
        self.assertEqual(fake_chat.message, "What is Intent OS?")

    def test_cloud_agent_uses_groq_for_web_chat_and_keeps_key_server_side(self):
        agent = CloudAgent()
        agent.api_key = ""
        agent.groq_api_key = "test-groq-key"
        agent.groq_model = "llama-test-model"
        with patch("groq.Groq") as groq_client:
            groq_client.return_value.chat.completions.create.return_value = SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="Groq-generated desktop explanation."),
                )],
            )
            answer = agent.reply(
                "What can the desktop app do?",
                [{"role": "user", "content": "Tell me about Intent OS."}],
            )

        self.assertEqual(answer, "Groq-generated desktop explanation.")
        groq_client.assert_called_once_with(api_key="test-groq-key", timeout=30, max_retries=0)
        call = groq_client.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(call["model"], "llama-test-model")
        self.assertIn("UNDERSTAND → OBSERVE → DECIDE → EXECUTE → VERIFY", call["messages"][0]["content"])
        self.assertEqual(call["messages"][1]["content"], "Tell me about Intent OS.")
        self.assertNotIn("test-groq-key", answer)

    def test_cloud_agent_prefers_groq_for_website_when_both_providers_are_configured(self):
        agent = CloudAgent()
        agent.api_key = "test-gemini-key"
        agent.groq_api_key = "test-groq-key"
        with (
            patch.object(agent, "_reply_with_groq", return_value="Groq website answer.") as groq_reply,
            patch.object(agent, "_reply_with_gemini", return_value="Gemini answer.") as gemini_reply,
        ):
            answer = agent.reply("What does the desktop app do?", [])

        self.assertEqual(answer, "Groq website answer.")
        groq_reply.assert_called_once_with("What does the desktop app do?", [])
        gemini_reply.assert_not_called()

    def test_cloud_agent_uses_gemini_for_website_only_if_groq_fails(self):
        agent = CloudAgent()
        agent.api_key = "test-gemini-key"
        agent.groq_api_key = "test-groq-key"
        with (
            patch.object(
                agent,
                "_reply_with_groq",
                side_effect=CloudAgentError("Groq is currently rate-limited or out of quota."),
            ) as groq_reply,
            patch.object(agent, "_reply_with_gemini", return_value="Gemini website backup.") as gemini_reply,
        ):
            answer = agent.reply("What does the desktop app do?", [])

        self.assertEqual(answer, "Gemini website backup.")
        groq_reply.assert_called_once()
        gemini_reply.assert_called_once_with("What does the desktop app do?", [])

    def test_cloud_agent_returns_clear_groq_rate_limit_error(self):
        agent = CloudAgent()
        agent.api_key = ""
        agent.groq_api_key = "test-groq-key"
        class ProviderError(Exception):
            status_code = 429

        with patch("groq.Groq") as groq_client:
            groq_client.return_value.chat.completions.create.side_effect = ProviderError(
                "private details test-groq-key",
            )
            with self.assertRaises(CloudAgentError) as error:
                agent.reply("hello", [])

        self.assertIn("rate-limited or out of quota", str(error.exception))
        self.assertNotIn("test-groq-key", str(error.exception))

    def test_cloud_agent_explains_cloudflare_block_without_revealing_key(self):
        agent = CloudAgent()
        agent.api_key = ""
        agent.groq_api_key = "test-groq-key"

        class ProviderResponse:
            text = '{"error_code":1010,"error_name":"browser_signature_banned"}'

        class ProviderError(Exception):
            status_code = 403
            response = ProviderResponse()

        with patch("groq.Groq") as groq_client:
            groq_client.return_value.chat.completions.create.side_effect = ProviderError(
                "private details test-groq-key",
            )
            with self.assertRaises(CloudAgentError) as error:
                agent.reply("hello", [])

        self.assertIn("network is blocking this Groq request", str(error.exception))
        self.assertNotIn("test-groq-key", str(error.exception))

    def test_logout_expires_the_session(self):
        self.client.post("/api/login", json={"username": "judge", "password": "unique-test-password"})
        self.assertEqual(self.client.post("/api/logout").status_code, 200)
        self.assertEqual(self.client.post("/api/agent", json={"action": "status"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()