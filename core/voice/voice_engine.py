# ============================================================
#  VOICE ENGINE — Audio Capture, STT, TTS & Concurrent Pipeline
#  Supports wake-word filtering ("System"), direct desktop commands,
#  fuzzy app & file opening, tab controls, and non-blocking Gemini.
# ============================================================

import logging
import threading
import time
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
from intent_platform.core.features.feature_manager import Feature, FeatureStatus, get_feature_manager
from intent_platform.core.agent.agent_controller import get_agent_controller
from intent_platform.core.events.event_dispatcher import InputEvent, EventPriority, get_event_dispatcher
from intent_platform.database.connection import db

logger = logging.getLogger("VoiceEngine")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class VoiceEngine:
    """
    Manages continuous voice recognition, wake-word activation,
    and non-blocking TTS responses with independent lifecycle management.
    """

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
        self._thread_lock = threading.Lock()

        # Interview Hooks
        self.interview_mode: bool = False
        self.interview_router = None
        self.interview_transcript_tap = None

        # Global singletons
        self._feature_manager = get_feature_manager()
        self._agent_controller = get_agent_controller()
        self._event_dispatcher = get_event_dispatcher()

        # Connect feature state listener
        self._feature_manager.signals.feature_toggled.connect(self._on_feature_toggled)

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
        except Exception as e:
            logger.warning(f"[VOICE] TTS init warning: {e}")
            self.tts_engine = None

    def _on_feature_toggled(self, feature: str, enabled: bool):
        if feature == Feature.VOICE.value:
            if enabled:
                logger.info("[VOICE] Feature toggled ON -> Resuming voice processing")
                self.set_paused(False)
            else:
                logger.info("[VOICE] Feature toggled OFF -> Pausing voice processing")
                self.set_paused(True)

    def set_interview_hooks(self, router, transcript_tap):
        self.interview_router = router
        self.interview_transcript_tap = transcript_tap

    def speak(self, text: str):
        """Asynchronously vocalizes feedback to the user without blocking any thread."""
        if not text:
            return

        def _run():
            try:
                import sys
                if sys.platform == 'win32':
                    try:
                        import pythoncom
                        pythoncom.CoInitialize()
                    except Exception:
                        pass
                engine = pyttsx3.init()
                engine.setProperty('rate', TTS_RATE)
                engine.setProperty('volume', TTS_VOLUME)
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.debug(f"[VOICE] TTS Speak error: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def set_paused(self, paused: bool):
        """Pause or resume voice command processing when auth or feature state changes."""
        self.is_paused = paused
        if self.is_running:
            if paused:
                if not self._feature_manager.is_enabled(Feature.VOICE):
                    self._feature_manager.set_status(Feature.VOICE, FeatureStatus.DISABLED.value)
                else:
                    self._feature_manager.set_status(Feature.VOICE, FeatureStatus.PAUSED.value)
            else:
                self._feature_manager.set_status(Feature.VOICE, FeatureStatus.RUNNING.value)

    def start(self):
        """Starts background voice listening loop with duplicate thread guard."""
        with self._thread_lock:
            if self.is_running and self.worker_thread and self.worker_thread.is_alive():
                logger.info("[VOICE] Worker thread already running (duplicate start prevented).")
                return

            self.is_running = True
            self.is_paused = not self._feature_manager.is_enabled(Feature.VOICE)
            self.worker_thread = threading.Thread(target=self._listen_loop, daemon=True, name="VoiceWorker")
            self.worker_thread.start()
            logger.info("[VOICE] Voice worker started.")
            if self._feature_manager.is_enabled(Feature.VOICE):
                self._feature_manager.set_status(Feature.VOICE, FeatureStatus.RUNNING.value)
            else:
                self._feature_manager.set_status(Feature.VOICE, FeatureStatus.DISABLED.value)

    def stop(self):
        """Stops background voice listener cleanly."""
        with self._thread_lock:
            self.is_running = False
            self.worker_thread = None
            self._feature_manager.set_status(Feature.VOICE, FeatureStatus.DISABLED.value)
            logger.info("[VOICE] Voice worker stopped.")

    def _listen_loop(self):
        try:
            mic = sr.Microphone()
        except Exception as e:
            logger.error(f"[VOICE] Microphone unavailable: {e}")
            self._feature_manager.set_status(Feature.VOICE, FeatureStatus.UNAVAILABLE.value)
            if self.on_status_change:
                self.on_status_change("Mic unavailable")
            return

        try:
            with mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
        except Exception as e:
            logger.warning(f"[VOICE] Ambient noise adjustment error: {e}")

        while self.is_running:
            if self.is_paused or not self._feature_manager.is_enabled(Feature.VOICE):
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

                if not self.is_running or self.is_paused or not self._feature_manager.is_enabled(Feature.VOICE):
                    continue

                try:
                    raw_text = self.recognizer.recognize_google(audio).strip().lower()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    logger.warning(f"[VOICE] STT request error: {e}")
                    time.sleep(0.5)
                    continue

                if not raw_text or self.is_paused or not self._feature_manager.is_enabled(Feature.VOICE):
                    continue

                duration = len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
                # Dispatch transcript processing in a dedicated background task
                # to guarantee the microphone listen loop is NEVER delayed!
                threading.Thread(
                    target=self._process_transcript,
                    args=(raw_text,),
                    kwargs={"meta": {"duration": duration}},
                    daemon=True
                ).start()

            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                logger.error(f"[VOICE] Listen loop error: {e}")
                time.sleep(0.5)

    def _process_transcript(self, raw_text: str, meta: Optional[dict] = None):
        """Checks for wake word 'System', agent activations, and dispatches intents asynchronously."""
        import re
        wake_pattern = r'\b' + re.escape(self.wake_word) + r'\b'
        has_wake = bool(re.search(wake_pattern, raw_text, re.IGNORECASE))
        
        # Strip conversational prefixes and wake word
        cleaned = re.sub(r'^[,\.\s]*(?:hey|ok|okay|hi|hello)?\s*' + re.escape(self.wake_word) + r'[,\.\s:]*', '', raw_text, flags=re.IGNORECASE).strip()
        cleaned = re.sub(wake_pattern, '', cleaned, flags=re.IGNORECASE).strip()
        eval_text = cleaned if cleaned else raw_text

        # ── 1. Voice Agent Activation & Deactivation Commands ──
        if any(act in eval_text for act in ("activate agent", "start assistant", "wake up", "start agent", "launch agent")):
            self._agent_controller.activate(source="voice")
            self.speak("AI Agent Activated")
            if self.on_command_detected:
                self.on_command_detected(raw_text, "AI Agent Activated")
            return
        elif any(act in eval_text for act in ("deactivate agent", "stop assistant", "sleep agent", "stop agent", "dismiss agent")):
            self._agent_controller.deactivate(source="voice")
            self.speak("AI Agent Deactivated")
            if self.on_command_detected:
                self.on_command_detected(raw_text, "AI Agent Deactivated")
            return

        # ── 2. Interview Mode Tap ──
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
                
                prediction = self.classifier.predict(eval_text)
                if prediction:
                    intent, confidence, target_arg = prediction
                    self._dispatch_intent(raw_text, intent, confidence, target_arg)
            return

        # ── 3. Standard Intent Classification & Dispatch ──
        prediction = self.classifier.predict(eval_text)
        if prediction:
            intent, confidence, target_arg = prediction
            self._dispatch_intent(raw_text, intent, confidence, target_arg)
            return

        # ── 4. Non-blocking Fallback to Gemini Multimodal Agent ──
        if has_wake or len(raw_text.split()) > 2:
            self._execute_gemini_query(raw_text, eval_text)

    def _dispatch_intent(self, raw_text: str, intent: str, confidence: float, target_arg: Optional[str]):
        """Dispatches recognized intent asynchronously via EventDispatcher."""
        def _action():
            return self._execute_intent(intent, target_arg)

        event = InputEvent(
            priority=EventPriority.USER_COMMAND,
            source="VOICE",
            event_type=intent,
            payload={"raw_text": raw_text, "confidence": confidence, "target_arg": target_arg}
        )

        def _on_done(result_msg):
            if result_msg:
                db.log_event("voice", raw_text, f"Intent: {intent} (Confidence: {confidence:.2f})")
                if self.on_command_detected:
                    self.on_command_detected(raw_text, result_msg)
                self.speak(result_msg)

        # Execute through EventDispatcher thread pool
        self._event_dispatcher.dispatch(event, lambda: _on_done(_action()))

    def _execute_gemini_query(self, raw_text: str, query_text: str):
        """Executes Gemini query in background without blocking any system."""
        def _run_gemini():
            try:
                self._agent_controller.set_processing("Thinking...")
                ai_reply = self.gemini_agent.query(query_text)
                if ai_reply:
                    db.log_event("voice_ai", raw_text, ai_reply[:100])
                    if self.on_command_detected:
                        self.on_command_detected(raw_text, ai_reply)
                    self.speak(ai_reply)
                self._agent_controller.set_idle("Ready")
            except Exception as e:
                logger.error(f"[VOICE] Gemini query error: {e}")
                self._agent_controller.set_idle("Ready")

        threading.Thread(target=_run_gemini, daemon=True, name="GeminiWorker").start()

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
            elif intent == 'next_tab':
                return actions.switch_tab('next')
            elif intent == 'previous_tab':
                return actions.switch_tab('previous')
            elif intent == 'reopen_closed_tab':
                return actions.reopen_closed_tab()

            # 3. Audio & System Volume
            elif intent == 'volume_up':
                return actions.change_volume('up', 10)
            elif intent == 'volume_down':
                return actions.change_volume('down', 10)
            elif intent == 'mute':
                return actions.mute_volume()
            elif intent == 'unmute':
                return actions.unmute_volume()

            # 4. Media Playback Controls
            elif intent == 'play_music':
                return actions.play_pause_media()
            elif intent == 'pause_music':
                return actions.play_pause_media()
            elif intent == 'next_track':
                return actions.next_track()
            elif intent == 'previous_track':
                return actions.previous_track()

            # 5. Window Management
            elif intent == 'minimize_window':
                return actions.minimize_window()
            elif intent == 'maximize_window':
                return actions.maximize_window()
            elif intent == 'close_window':
                return actions.close_window()
            elif intent == 'show_desktop':
                return actions.show_desktop()

            # 6. Utilities & Productivity
            elif intent == 'take_screenshot':
                return actions.take_screenshot()
            elif intent == 'scroll_up':
                return actions.scroll_page('up')
            elif intent == 'scroll_down':
                return actions.scroll_page('down')
            elif intent == 'zoom_in':
                return actions.zoom_in()
            elif intent == 'zoom_out':
                return actions.zoom_out()
            elif intent == 'reset_zoom':
                return actions.reset_zoom()

            # 7. System Power Commands
            elif intent == 'lock_workstation':
                return actions.lock_workstation()

        except Exception as e:
            logger.error(f"[VOICE] Action execution failed for {intent}: {e}")
            return f"Error executing {intent}: {e}"

        return None
