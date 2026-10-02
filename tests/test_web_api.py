import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import google.generativeai as genai

from web.backend.cloud_agent import CloudAgent, CloudAgentError
from web.backend.main import app


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "WEB_DEMO_USERNAME": "judge",
            "WEB_DEMO_PASSWORD": "unique-test-password",
            "WEB_SESSION_SECRET": "test-only-session-secret-at-least-32-chars",
            "GEMINI_API_KEY": "test-only-key",
        })
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_status_lists_web_and_desktop_capabilities_without_secrets(self):
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["web_login_configured"])
        self.assertTrue(body["gemini_configured"])
        self.assertFalse(body["authenticated"])
        self.assertEqual(body["status"], "available")
        self.assertIn("camera and gesture control", body["desktop_only"])
        self.assertNotIn("test-only-key", response.text)

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

    def test_chat_missing_gemini_key_returns_safe_setup_error(self):
        self.client.post("/api/login", json={"username": "judge", "password": "unique-test-password"})
        with patch("web.backend.main.cloud_agent.api_key", ""):
            response = self.client.post("/api/chat", json={"message": "hello"})
        self.assertEqual(response.status_code, 503)
        self.assertIn("GEMINI_API_KEY", response.json()["detail"]["message"])
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

    def test_logout_expires_the_session(self):
        self.client.post("/api/login", json={"username": "judge", "password": "unique-test-password"})
        self.assertEqual(self.client.post("/api/logout").status_code, 200)
        self.assertEqual(self.client.post("/api/agent", json={"action": "status"}).status_code, 401)


if __name__ == "__main__":
    unittest.main()