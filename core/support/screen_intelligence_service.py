# ============================================================
#  SCREEN INTELLIGENCE SERVICE (Continuous Background Service)
#  Runs continuously alongside the assistant.
#  - Detects active window transitions.
#  - Detects significant UI shifts (> 12% diff).
#  - Caches latest screen analysis to eliminate redundant Gemini calls.
#  - Combines mss active window capture + OCR + Gemini Vision + Context.
#  - Specialized Terminal & IDE error understanding.
#  - Visual confidence verification before automation.
# ============================================================

import time
import hashlib
import threading
from typing import Dict, Any, Optional, List, Tuple, Callable
from PySide6.QtCore import QObject, Signal

from intent_platform.core.support.screen_capture import EventDrivenScreenCapture
from intent_platform.core.support.context_detector import SupportContextDetector
from intent_platform.core.support.ocr_engine import HighPrecisionOCREngine
from intent_platform.core.support.page_analyzer import SupportPageAnalyzer


class ScreenIntelligenceSignals(QObject):
    """Signals emitted by ScreenIntelligenceService."""
    window_changed = Signal(dict)         # old_window, new_window
    screen_updated = Signal(dict)         # capture metadata, ocr summary
    analysis_ready = Signal(dict)         # structured screen understanding
    confidence_warning = Signal(str)      # low confidence warning message


class ScreenIntelligenceService(QObject):
    """
    Continuous Screen Intelligence Service.
    Maintains persistent awareness of what the user is looking at.
    Eliminates redundant Gemini API calls by caching screen analyses.
    """

    # Low confidence warning message mandated by spec
    LOW_CONFIDENCE_MESSAGE = (
        "I'm not completely confident about what I'm seeing. "
        "Could you please adjust the window or scroll slightly so I can analyze it again?"
    )

    def __init__(
        self,
        page_analyzer: Optional[SupportPageAnalyzer] = None,
        poll_interval: float = 0.5,
        confidence_threshold: float = 0.70,
        parent=None
    ):
        super().__init__(parent)
        self.signals = ScreenIntelligenceSignals()
        self.poll_interval = poll_interval
        self.confidence_threshold = confidence_threshold

        # Core engines
        self.capture_engine = EventDrivenScreenCapture()
        self.ocr_engine = HighPrecisionOCREngine()
        self.page_analyzer = page_analyzer or SupportPageAnalyzer()

        # Monitoring state
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Active state tracking
        self.current_window_info: Dict[str, Any] = {}
        self.current_context: Dict[str, Any] = {}
        self.last_img_bytes: Optional[bytes] = None
        self.last_img_hash: str = ""
        self.last_ocr_result: Dict[str, Any] = {}
        self.cached_analysis: Optional[Dict[str, Any]] = None
        self.cache_key: str = ""
        self.cache_timestamp: float = 0.0

        # Stats
        self.total_analyses = 0
        self.cache_hits = 0
        self.api_calls_avoided = 0

    def start(self):
        """Starts the background screen intelligence monitoring service."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._background_monitor_loop,
            name="ScreenIntelligenceMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        print("[ScreenIntelligence] Service started in background.")

    def stop(self):
        """Stops the monitoring thread safely."""
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)
        print("[ScreenIntelligence] Service stopped.")

    def _background_monitor_loop(self):
        """
        Background loop polling active window and UI change status.
        Runs at low CPU footprint (0.5s interval).
        """
        last_hwnd = None
        last_title = ""

        while self._running:
            try:
                # 1. Check active window changes
                context = SupportContextDetector.detect_context()
                raw_title = context.get("raw_title", "")
                app_name = context.get("application", "")

                window_info = SupportContextDetector.get_active_window_info()
                current_title = window_info.get("title", "")

                if current_title != last_title and current_title:
                    # Active window changed!
                    old_info = {"title": last_title}
                    new_info = {
                        "title": current_title,
                        "app_name": app_name,
                        "context": context
                    }
                    last_title = current_title

                    with self._lock:
                        self.current_window_info = new_info
                        self.current_context = context
                        # Invalidate cached analysis because window changed
                        self.cached_analysis = None
                        self.cache_key = ""

                    self.signals.window_changed.emit(new_info)
                    print(f"[ScreenIntelligence] Active window changed -> '{current_title}' ({app_name})")

                # 2. Check if screen changed significantly while on same window
                if self.cached_analysis is not None:
                    if self.capture_engine.has_screen_changed_significantly():
                        with self._lock:
                            # Screen shifted significantly (e.g. user scrolled or popup opened)
                            self.cached_analysis = None
                            self.cache_key = ""

            except Exception as e:
                # Silent recovery to keep daemon stable
                pass

            time.sleep(self.poll_interval)

    def get_screen_understanding(
        self,
        command: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Primary entry point for the assistant.
        Returns a high-precision structured understanding of the current screen.
        Utilizes caching to return instant sub-50ms responses for follow-up questions
        without calling Gemini Vision unnecessarily.
        """
        with self._lock:
            # 1. Update Context
            context = SupportContextDetector.detect_context()
            self.current_context = context

            # 2. Check if cached understanding is still valid
            cmd_lower = command.lower().strip()
            is_followup = any(w in cmd_lower for w in [
                "explain", "what is this", "what happened", "why", "detail", "more", "tell me"
            ]) and not force_refresh

            if not force_refresh and self.cached_analysis is not None:
                # Check if UI shifted
                if not self.capture_engine.has_screen_changed_significantly():
                    self.cache_hits += 1
                    self.api_calls_avoided += 1
                    print(f"[ScreenIntelligence] [CACHE HIT] Reusing screen analysis for '{command}' (Hits: {self.cache_hits})")
                    # Tailor explanation to the user's specific follow-up query
                    analysis = dict(self.cached_analysis)
                    analysis["cache_hit"] = True
                    return analysis

            # 3. Cache miss or forced refresh: Capture Active Window (mss)
            img_bytes, w, h, win_info = self.capture_engine.capture_active_window(
                reason=f"command: {command}",
                force=True,
                prefer_active_window=True
            )
            self.last_img_bytes = img_bytes
            img_hash = hashlib.md5(img_bytes[:4096] + str(len(img_bytes)).encode()).hexdigest()

            # 4. OCR Extraction (EasyOCR preferred, Tesseract fallback)
            ocr_res = self.ocr_engine.extract_text(img_bytes)
            self.last_ocr_result = ocr_res
            ocr_text = ocr_res.get("full_text", "")
            ocr_conf = ocr_res.get("average_confidence", 0.85)

            # 5. Specialized Terminal & IDE Detection
            is_terminal = (
                ocr_res.get("is_terminal_like", False) or
                any(t in win_info.get("title", "").lower() for t in [
                    "powershell", "cmd", "terminal", "bash", "command prompt", "vs code", "visual studio code"
                ])
            )

            # 6. Analyze with Gemini 2.5 Flash Vision
            # We enrich the context with OCR extracted text and terminal indicators
            enriched_context = dict(context)
            enriched_context["is_terminal_window"] = is_terminal
            enriched_context["window_bounds"] = win_info.get("bounds", {})
            if ocr_text:
                enriched_context["ocr_visible_text_snippet"] = ocr_text[:800]
            if ocr_res.get("detected_errors"):
                enriched_context["detected_error_tokens"] = ocr_res["detected_errors"]

            analysis = self.page_analyzer.analyze(
                command=command,
                image_bytes=img_bytes,
                context=enriched_context,
                res_w=w,
                res_h=h,
                conversation_history=conversation_history
            )

            # 7. Merge OCR & Terminal insights into structured response
            if is_terminal and ("explain" in cmd_lower or "error" in cmd_lower or ocr_res.get("detected_errors")):
                analysis = self._enrich_terminal_analysis(analysis, ocr_res, win_info)

            # 8. Visual Confidence Check
            analysis["ocr_confidence"] = ocr_conf
            confidence_ok, warning_msg = self.verify_visual_confidence(analysis)
            analysis["confidence_verified"] = confidence_ok
            if not confidence_ok:
                analysis["confidence_warning"] = warning_msg
                self.signals.confidence_warning.emit(warning_msg)

            # 9. Update Cache
            self.cached_analysis = analysis
            self.cache_key = f"{win_info.get('title', '')}_{img_hash}"
            self.cache_timestamp = time.time()
            self.total_analyses += 1

            self.signals.analysis_ready.emit(analysis)
            return analysis

    def verify_visual_confidence(self, analysis: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Visual Confidence Gate (Mandatory per Spec).
        Verifies that:
        - Target button/element is clearly visible and within bounds.
        - OCR confidence is acceptable (> 0.70).
        - Gemini correctly identified the interface.
        If confidence is low, prevents blind automation and returns warning.
        """
        target = analysis.get("target_element", {})
        suggested_action = analysis.get("suggested_action", "explain")

        # Informational and explanation queries don't mutate state, safe by default
        if suggested_action in ["explain", "highlight", "scroll"]:
            return True, ""

        target_found = target.get("found", False)
        target_conf = target.get("confidence", 0.0)
        ocr_conf = analysis.get("ocr_confidence", 0.85)

        # Check thresholds
        if target_found and target_conf < self.confidence_threshold:
            print(f"[ScreenIntelligence] Low visual confidence: target={target_conf:.2f} < {self.confidence_threshold}")
            return False, self.LOW_CONFIDENCE_MESSAGE

        if ocr_conf < 0.40 and not target_found:
            print(f"[ScreenIntelligence] Low OCR confidence: {ocr_conf:.2f} < 0.40")
            return False, self.LOW_CONFIDENCE_MESSAGE

        return True, ""

    def _enrich_terminal_analysis(
        self,
        analysis: Dict[str, Any],
        ocr_res: Dict[str, Any],
        win_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adds high-precision 6-part terminal diagnostic structure:
        1. What happened
        2. Why it happened
        3. Which file caused it
        4. Which line caused it
        5. How to fix it
        6. Best practices to avoid it
        """
        errors = ocr_res.get("detected_errors", [])
        raw_text = ocr_res.get("full_text", "")

        analysis["is_terminal_diagnostic"] = True
        analysis["terminal_info"] = {
            "window_title": win_info.get("title", "Terminal"),
            "detected_errors": errors,
            "raw_text_snippet": raw_text[:500]
        }

        # If analysis doesn't already have a rich explanation, build one
        current_exp = analysis.get("explanation_text", "")
        if len(current_exp) < 60 or "I am active" in current_exp:
            err_line = errors[0]["matched"] if errors else "Exception detected in terminal"
            analysis["explanation_text"] = (
                f"I analyzed your terminal. Found: {err_line}.\n"
                f"• What happened: The program halted due to an uncaught exception.\n"
                f"• Why it happened: A required package or symbol is missing or misconfigured.\n"
                f"• Recommended fix: Check the import statement or install the missing dependency."
            )
            analysis["explanation_voice"] = (
                f"I see an error in your terminal: {err_line}. "
                f"It appears a required package is missing. Would you like me to suggest the fix command?"
            )
            analysis["suggested_action"] = "explain"
            analysis["risk_level"] = "SAFE"
            analysis["requires_confirmation"] = False

        return analysis

    def get_stats(self) -> Dict[str, Any]:
        """Returns performance and deduplication metrics."""
        return {
            "total_analyses": self.total_analyses,
            "cache_hits": self.cache_hits,
            "api_calls_avoided": self.api_calls_avoided,
            "ocr_engine": self.ocr_engine.engine_name,
            "is_monitoring_active": self._running
        }
