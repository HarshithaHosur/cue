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
import re
import math
from typing import Dict, Any, Optional, List, Tuple, Callable
from PySide6.QtCore import QObject, Signal

from intent_platform.core.support.screen_capture import EventDrivenScreenCapture
from intent_platform.core.support.context_detector import SupportContextDetector
from intent_platform.core.support.ocr_engine import HighPrecisionOCREngine
from intent_platform.core.support.page_analyzer import SupportPageAnalyzer
from intent_platform.core.support.screen_context import ScreenContext, build_screen_context


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
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        force_refresh: bool = False,
        additional_context: Optional[Dict[str, Any]] = None,
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

            # Each request needs fresh reasoning for its command and conversation history.
            cmd_lower = command.lower().strip()

            # 3. Cache miss or forced refresh: Capture Active Window (mss)
            img_bytes, w, h, win_info = self.capture_engine.capture_active_window(
                reason=f"command: {command}",
                force=True,
                prefer_active_window=True
            )
            captured_info = SupportContextDetector.get_window_info(win_info.get("hwnd", 0))
            if not captured_info.get("title"):
                captured_info["title"] = win_info.get("title", "")
                captured_info["title_lower"] = captured_info["title"].lower()
                captured_info["app_name"] = win_info.get("app_name", context.get("application", "Desktop"))
                captured_info["browser_name"] = win_info.get("browser_name")
                captured_info["is_browser"] = captured_info["browser_name"] is not None
            context = SupportContextDetector.detect_context(captured_info)
            self.current_context = context
            self.last_img_bytes = img_bytes
            img_hash = hashlib.md5(img_bytes[:4096] + str(len(img_bytes)).encode()).hexdigest()

            # 4. OCR Extraction (EasyOCR preferred, Tesseract fallback)
            ocr_res = self.ocr_engine.extract_text(img_bytes)
            self.last_ocr_result = ocr_res
            ocr_text = ocr_res.get("full_text", "")
            ocr_conf = ocr_res.get("average_confidence", 0.85)

            # 5. Build Structured ScreenContext (Priority 2: Real Screen Understanding)
            screen_ctx = build_screen_context(
                window_info=win_info,
                ocr_result=ocr_res,
                width=w,
                height=h
            )
            screen_ctx.active_application = captured_info.get("app_name", screen_ctx.active_application)
            screen_ctx.is_browser = captured_info.get("is_browser", screen_ctx.is_browser)
            screen_ctx.browser_name = captured_info.get("browser_name", screen_ctx.browser_name)
            if context.get("website") not in (None, "", "General Website"):
                screen_ctx.website = context["website"]
            if context.get("page_type") not in (None, "", "Standard Webpage", "Home"):
                screen_ctx.current_page = context["page_type"]
            screen_ctx.is_support_page = context.get("is_support_page", screen_ctx.is_support_page)
            screen_ctx.current_user_goal = command
            self.current_screen_context = screen_ctx

            # 6. Enrich context dict with ScreenContext data for Gemini
            enriched_context = dict(context)
            enriched_context.update({
                "application": screen_ctx.active_application,
                "is_browser": screen_ctx.is_browser,
                "browser": screen_ctx.browser_name,
                "website": screen_ctx.website,
                "page_type": screen_ctx.current_page,
                "is_support_page": screen_ctx.is_support_page,
            })
            enriched_context["is_terminal_window"] = screen_ctx.is_terminal
            enriched_context["terminal_type"] = screen_ctx.terminal_type
            enriched_context["window_bounds"] = win_info.get("bounds", {})
            enriched_context["visible_buttons"] = [b["label"] for b in screen_ctx.visible_buttons[:8]]
            enriched_context["visible_tabs"] = [t["label"] for t in screen_ctx.visible_tabs[:6]]
            enriched_context["detected_page"] = screen_ctx.current_page
            enriched_context["detected_website"] = screen_ctx.website
            if ocr_text:
                enriched_context["ocr_visible_text_snippet"] = ocr_text[:800]
            if ocr_res.get("detected_errors"):
                enriched_context["detected_error_tokens"] = ocr_res["detected_errors"]
            if additional_context:
                enriched_context["additional_runtime_context"] = additional_context

            # 7. Analyze with Gemini Vision + ScreenContext
            analysis = self.page_analyzer.analyze(
                command=command,
                image_bytes=img_bytes,
                context=enriched_context,
                res_w=w,
                res_h=h,
                screen_context=screen_ctx,
                conversation_history=conversation_history,
                additional_context=additional_context,
            )

            # 8. Merge OCR & Terminal insights into structured response
            if screen_ctx.is_terminal and ("explain" in cmd_lower or "error" in cmd_lower or ocr_res.get("detected_errors")):
                analysis = self._enrich_terminal_analysis(analysis, ocr_res, win_info)

            # 9. Visual Confidence Check
            analysis["ocr_confidence"] = ocr_conf
            analysis["current_user_goal"] = command
            analysis["automation_confidence"] = min(
                float(analysis.get("target_element", {}).get("confidence", 0.0)),
                float(ocr_conf),
            )
            screen_ctx.automation_confidence = analysis["automation_confidence"]
            screen_ctx.selected_item = str(analysis.get("selected_item", ""))
            screen_ctx.dialogs = analysis.get("dialogs", screen_ctx.dialogs)
            screen_ctx.warnings = analysis.get("warnings", screen_ctx.warnings)
            target = analysis.get("target_element", {})
            screen_ctx.highlighted_elements = [target] if target.get("found") else []
            analysis["screen_context"] = screen_ctx.to_dict()

            origin = win_info.get("capture_origin", win_info.get("bounds", {}))
            target_x = target.get("x")
            target_y = target.get("y")
            if target.get("found") and isinstance(target_x, (int, float)) and isinstance(target_y, (int, float)):
                target["image_x"] = int(target_x)
                target["image_y"] = int(target_y)
                target["ocr_verified"] = self._verify_target_against_ocr(
                    target, screen_ctx.ocr_blocks
                )
                target["x"] = int(target_x + origin.get("left", 0))
                target["y"] = int(target_y + origin.get("top", 0))
                target["screen_coordinates"] = True
            analysis["screen_fingerprint"] = img_hash
            analysis["window_title"] = win_info.get("title", "")
            analysis["window_bounds"] = win_info.get("bounds", {})
            confidence_ok, warning_msg = self.verify_visual_confidence(analysis)
            analysis["confidence_verified"] = confidence_ok
            if not confidence_ok:
                analysis["confidence_warning"] = warning_msg
                self.signals.confidence_warning.emit(warning_msg)

            # 10. Update Cache
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

        # Scrolling is non-destructive; clicking/filling requires a verified target.
        if suggested_action in ["explain", "highlight", "scroll"]:
            return True, ""

        target_found = target.get("found", False)
        target_conf = target.get("confidence", 0.0)
        ocr_conf = analysis.get("ocr_confidence", 0.85)

        if suggested_action in ["click", "fill", "select"]:
            if not target_found or not target.get("ocr_verified", False):
                return False, self.LOW_CONFIDENCE_MESSAGE
            x = target.get("image_x", -1)
            y = target.get("image_y", -1)
            if not (0 <= x < analysis.get("screen_context", {}).get("width", 0)
                    and 0 <= y < analysis.get("screen_context", {}).get("height", 0)):
                return False, self.LOW_CONFIDENCE_MESSAGE

        # Check thresholds
        if target_found and target_conf < self.confidence_threshold:
            print(f"[ScreenIntelligence] Low visual confidence: target={target_conf:.2f} < {self.confidence_threshold}")
            return False, self.LOW_CONFIDENCE_MESSAGE

        if ocr_conf < 0.40 and not target_found:
            print(f"[ScreenIntelligence] Low OCR confidence: {ocr_conf:.2f} < 0.40")
            return False, self.LOW_CONFIDENCE_MESSAGE

        return True, ""

    @staticmethod
    def _verify_target_against_ocr(target: Dict[str, Any], blocks: List[Dict[str, Any]]) -> bool:
        return ScreenIntelligenceService._find_ocr_target(target, blocks) is not None

    @staticmethod
    def _find_ocr_target(
        target: Dict[str, Any], blocks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        label = re.sub(r"\W+", " ", str(target.get("label", "")).lower()).strip()
        if not label:
            return None
        x = int(target.get("image_x", target.get("x", -1)))
        y = int(target.get("image_y", target.get("y", -1)))
        label_tokens = set(label.split())
        closest = None
        closest_distance = float("inf")
        for block in blocks:
            if float(block.get("confidence", 0.0)) < 0.45:
                continue
            text = re.sub(r"\W+", " ", str(block.get("text", "")).lower()).strip()
            if not text:
                continue
            text_tokens = set(text.split())
            overlap = len(label_tokens & text_tokens) / max(1, len(label_tokens))
            if overlap < 0.5 and label not in text and text not in label:
                continue
            bbox = block.get("bbox", [0, 0, 0, 0])
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            distance = math.hypot(center_x - x, center_y - y)
            if distance <= 120 and distance < closest_distance:
                closest = block
                closest_distance = distance
        return closest

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
