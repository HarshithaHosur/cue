import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPOSITORY_PARENT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_PARENT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_PARENT))

from intent_platform.core.voice.classifier import VoiceIntentClassifier
from intent_platform.core.voice.voice_engine import VoiceEngine
from intent_platform.core.automation import actions
from intent_platform.ui.main_window import MainWindow
import intent_platform.core.voice.voice_engine as voice_engine_module


class ImmediateDispatcher:
    def dispatch(self, _event, action):
        action()


class CustomerSupportRoutingTests(unittest.TestCase):
    def test_support_phrases_classify_to_shared_agent_intent(self):
        classifier = VoiceIntentClassifier()
        phrases = (
            "Open customer support",
            "Open customer care",
            "I need customer support",
            "I need help",
            "Raise a complaint",
            "I want to complain about this order",
            "Yes, please",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                result = classifier.predict(phrase)
                self.assertIsNotNone(result)
                self.assertEqual(result[0], "support_agent")

    def test_voice_support_intent_reaches_shared_ui_callback_once(self):
        delivered = []
        with (
            patch.object(VoiceEngine, "_init_tts"),
            patch.object(voice_engine_module, "GeminiAgent"),
            patch.object(voice_engine_module.db, "log_event"),
        ):
            engine = VoiceEngine(on_command_detected=lambda text, result: delivered.append((text, result)))
        engine._event_dispatcher = ImmediateDispatcher()

        engine._dispatch_intent("Open customer care", "support_agent", 1.0, None)

        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0][0], "Open customer care")
        self.assertIn("Customer Support Agent", delivered[0][1])

    def test_voice_confirmation_reaches_pending_shared_support_action(self):
        delivered = []
        dashboard = SimpleNamespace(add_user_message=delivered.append)
        support_agent = SimpleNamespace(
            safety_manager=SimpleNamespace(has_pending_action=lambda: True),
            active_tech_action=None,
            handle_user_request=lambda text: delivered.append(("request", text)),
        )
        window = SimpleNamespace(
            page_support=SimpleNamespace(agent_dashboard=dashboard),
            support_agent=support_agent,
        )

        MainWindow._route_to_support_agent(window, "Yes, please.")

        self.assertEqual(delivered, ["Yes, please.", ("request", "Yes, please.")])

    def test_browser_launch_uses_default_browser_without_hardcoded_chrome(self):
        with patch("intent_platform.core.automation.actions.webbrowser.open", return_value=True) as open_default:
            result = actions.open_item("browser")
        self.assertEqual(result, "Opened the default browser.")
        open_default.assert_called_once_with("about:blank", new=2)

    def test_amazon_customer_care_opens_help_page(self):
        with patch("intent_platform.core.automation.actions.webbrowser.open", return_value=True) as open_default:
            result = actions.open_item("Amazon customer care")
        self.assertEqual(result, "Opened Amazon Customer Care help page.")
        open_default.assert_called_once_with("https://www.amazon.in/gp/help/customer/display.html", new=2)


if __name__ == "__main__":
    unittest.main()