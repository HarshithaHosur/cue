# ============================================================
#  VOICE ENGINE — Audio Capture, STT, TTS & Command Pipeline
#  Supports wake-word filtering ("System"), direct desktop commands,
#  fuzzy app & file opening, tab controls, and Gemini fallback.
# ============================================================

import time
import threading
from typing import Optional, Callable

import speech_recognition as sr
import pyttsx3

from intent_platform.config.settings import (
    VOICE_LISTEN_TIMEOUT,
    VOICE_PHRASE_LIMIT,
    TTS_RATE,
    TTS_VOLUME,
    WAKE_WORD
)
from intent_platform.core.voice.classifier import VoiceIntentClassifier
from intent_platform.core.automation import actions
from intent_platform.core.ai.gemini_service import GeminiAgent
from intent_platform.database.connection import db


class VoiceEngine:
    """Manages continuous voice recognition, wake-word activation, and TTS responses."""

    def __init__(
        self,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_command_detected: Optional[Callable[[str, str], None]] = None
    ):
        self.on_status_change = on_status_change
        self.on_command_detected = on_command_detected
        self.classifier = VoiceIntentClassifier()
        self.gemini_agent = GeminiAgent()

        self.recognizer = sr.Recognizer()
        # High accuracy noise filtering & silence tuning
        self.recognizer.pause_threshold = 0.8
        self.recognizer.non_speaking_duration = 0.4
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 250

        self.is_running = False
        self.is_paused = False  # Set to True when authentication is lost
        self.wake_word = WAKE_WORD.lower()
        self.worker_thread: Optional[threading.Thread] = None
        
        # Interview Hooks
        self.interview_mode: bool = False
        self.interview_router = None
        self.interview_transcript_tap = None

        # TTS init
        self._init_tts()

    def _init_tts(self):
        try:
            self.tts_engine = pyttsx3.init()
            voices = self.tts_engine.getProperty('voices')
            for v in voices:
                if any(n in v.name.lower() for n in ['female', 'zira', 'samantha', 'hazel', 'david']):
                    self.tts_engine.setProperty('voice', v.id)
                    break
            self.tts_engine.setProperty('rate', TTS_RATE)
            self.tts_engine.setProperty('volume', TTS_VOLUME)
        except Exception:
            self.tts_engine = None

    def set_interview_hooks(self, router, transcript_tap):
        self.interview_router = router
        self.interview_transcript_tap = transcript_tap

    def speak(self, text: str):
        """Asynchronously vocalizes feedback to the user."""
        if not text:
            return

        def _run():
            try:
                engine = pyttsx3.init()
                engine.setProperty('rate', TTS_RATE)
                engine.setProperty('volume', TTS_VOLUME)
                engine.say(text)
                engine.runAndWait()
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def set_paused(self, paused: bool):
        """Pause or resume voice command processing when auth changes."""
        self.is_paused = paused

    def start(self):
        """Starts background voice listening loop."""
        if self.is_running:
            return
        self.is_running = True
        self.is_paused = False
        self.worker_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        """Stops background voice listener."""
        self.is_running = False

    def _listen_loop(self):
        try:
            mic = sr.Microphone()
        except Exception:
            if self.on_status_change:
                self.on_status_change("Mic unavailable")
            return

        try:
            with mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
        except Exception:
            pass

        while self.is_running:
            if self.is_paused:
                time.sleep(0.2)
                continue

            try:
                if self.on_status_change:
                    self.on_status_change("Listening")

                with mic as source:
                    audio = self.recognizer.listen(
                        source,
                        timeout=VOICE_LISTEN_TIMEOUT,
                        phrase_time_limit=VOICE_PHRASE_LIMIT
                    )

                if not self.is_running or self.is_paused:
                    continue

                try:
                    raw_text = self.recognizer.recognize_google(audio).strip().lower()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    time.sleep(1)
                    continue

                if not raw_text or self.is_paused:
                    continue

                duration = len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
                self._process_transcript(raw_text, meta={"duration": duration})

            except sr.WaitTimeoutError:
                continue
            except Exception:
                time.sleep(0.5)

    def _process_transcript(self, raw_text: str, meta: Optional[dict] = None):
        """Checks for wake word 'System' and dispatches intent."""
        import re
        import time
        wake_pattern = r'\b' + re.escape(self.wake_word) + r'\b'
        has_wake = bool(re.search(wake_pattern, raw_text, re.IGNORECASE))
        # Strip conversational prefixes and wake word
        cleaned = re.sub(r'^[,\.\s]*(?:hey|ok|okay|hi|hello)?\s*' + re.escape(self.wake_word) + r'[,\.\s:]*', '', raw_text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(wake_pattern, '', cleaned, flags=re.IGNORECASE).strip()

        eval_text = cleaned if cleaned else raw_text
        
        if self.interview_mode:
            duration = meta.get("duration", 0) if meta else 0
            if self.interview_transcript_tap:
                self.interview_transcript_tap({
                    "text": raw_text,
                    "duration": duration,
                    "ts": time.time(),
                    "has_wake": has_wake
                })
            
            if has_wake:
                if self.interview_router:
                    action_msg = self.interview_router.handle(eval_text)
                    if action_msg:
                        db.log_event("voice_interview", raw_text, action_msg)
                        if self.on_command_detected:
                            self.on_command_detected(raw_text, action_msg)
                        self.speak(action_msg)
                        return
                
                # Fallback to normal classifier for wake words even in interview mode if router didn't handle it
                prediction = self.classifier.predict(eval_text)
                if prediction:
                    intent, confidence, target_arg = prediction
                    action_msg = self._execute_intent(intent, target_arg)
                    if action_msg:
                        db.log_event("voice", raw_text, f"Intent: {intent} (Confidence: {confidence:.2f})")
                        if self.on_command_detected:
                            self.on_command_detected(raw_text, action_msg)
                        self.speak(action_msg)
            
            # If no wake word or nothing handled it in interview mode, suppress Gemini fallback and TTS
            return

        prediction = self.classifier.predict(eval_text)
        if prediction:
            intent, confidence, target_arg = prediction
            action_msg = self._execute_intent(intent, target_arg)
            if action_msg:
                db.log_event("voice", raw_text, f"Intent: {intent} (Confidence: {confidence:.2f})")
                if self.on_command_detected:
                    self.on_command_detected(raw_text, action_msg)
                self.speak(action_msg)
                return

        # Fallback to Gemini multimodal agent for conversational / complex queries
        if has_wake or len(raw_text.split()) > 2:
            ai_reply = self.gemini_agent.query(eval_text)
            if ai_reply:
                db.log_event("voice_ai", raw_text, ai_reply[:100])
                if self.on_command_detected:
                    self.on_command_detected(raw_text, ai_reply)
                self.speak(ai_reply)

    def _execute_intent(self, intent: str, target_arg: Optional[str] = None) -> Optional[str]:
        """Routes recognized voice intent to automation action."""
        try:
            # 1. Open items / files / apps
            if intent == 'open_item' and target_arg:
                return actions.open_item(target_arg)
            elif intent == 'open_chrome':
                return actions.open_item('chrome')
            elif intent == 'open_spotify':
                return actions.open_item('spotify')
            elif intent == 'open_vscode':
                return actions.open_item('code')
            elif intent == 'open_calculator':
                return actions.open_item('calculator')
            elif intent == 'open_notepad':
                return actions.open_item('notepad')
            elif intent == 'open_file_explorer':
                return actions.open_item('explorer')

            # 2. Browser Tab Controls
            elif intent == 'open_new_tab':
                return actions.open_new_tab()
            elif intent == 'close_tab':
                return actions.close_tab()
            elif intent == 'close_current_tab':
                return actions.close_current_tab()
            elif intent == 'close_first_tab':
                return actions.close_first_tab()
            elif intent == 'close_all_tabs':
                return actions.close_all_tabs()
            elif intent == 'switch_to_first_tab':
                return actions.switch_to_first_tab()
            elif intent == 'switch_to_last_tab':
                return actions.switch_to_last_tab()
            elif intent == 'next_tab':
                return actions.next_tab()
            elif intent == 'previous_tab':
                return actions.previous_tab()

            # 3. Screenshot
            elif intent == 'take_screenshot':
                return actions.take_screenshot()

            # 4. Media & Volume
            elif intent == 'volume_up':
                return actions.change_volume('up', 5)
            elif intent == 'volume_down':
                return actions.change_volume('down', 5)
            elif intent == 'mute':
                return actions.mute_volume()
            elif intent == 'play_pause':
                return actions.play_pause()
            elif intent == 'next_song':
                return actions.next_song()
            elif intent == 'previous_song':
                return actions.previous_song()

            # 5. Window Management
            elif intent == 'close_window':
                return actions.close_active_window()
            elif intent == 'minimize_window':
                return actions.minimize_window()
            elif intent == 'maximize_window':
                return actions.maximize_window()
            elif intent == 'switch_window':
                return actions.switch_window()
            elif intent == 'show_desktop':
                return actions.show_desktop()

            # 6. Presentation
            elif intent == 'start_presentation':
                return actions.start_presentation()
            elif intent == 'stop_presentation':
                return actions.stop_presentation()
            elif intent == 'next_slide':
                return actions.next_slide()
            elif intent == 'previous_slide':
                return actions.previous_slide()

            # 7. AI Customer Support Agent
            elif intent == 'support_agent':
                return "Routing to AI Support Agent"

        except Exception as e:
            return f"Error executing command: {str(e)}"

        return None
