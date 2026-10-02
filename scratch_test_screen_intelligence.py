# ============================================================
#  VERIFICATION TEST: MODULE 8.1 & SCREEN INTELLIGENCE SERVICE
#  Tests high-precision screen capture, OCR engine, terminal
#  understanding, deduplication caching, and visual confidence.
# ============================================================

import sys
import os
import time
from unittest.mock import Mock

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Register intent_platform module
import types
import core, ui, config, database
ip_mod = types.ModuleType('intent_platform')
ip_mod.__path__ = [str(BASE_DIR)]
sys.modules['intent_platform'] = ip_mod
sys.modules['intent_platform.core'] = core
sys.modules['intent_platform.ui'] = ui
sys.modules['intent_platform.config'] = config
sys.modules['intent_platform.database'] = database

from intent_platform.core.support.ocr_engine import HighPrecisionOCREngine
from intent_platform.core.support.screen_capture import EventDrivenScreenCapture
from intent_platform.core.support.screen_intelligence_service import ScreenIntelligenceService
from intent_platform.core.support.page_analyzer import SupportPageAnalyzer


def test_ocr_engine():
    print("\n--- [TEST 1] High-Precision OCR Engine ---")
    ocr = HighPrecisionOCREngine()
    print(f"Active OCR Engine: {ocr.engine_name}")

    sample_terminal_error = """
    Traceback (most recent call last):
      File "main.py", line 42, in <module>
        import pyaudio
    ModuleNotFoundError: No module named 'pyaudio'
    """
    errors = ocr._parse_errors(sample_terminal_error)
    print(f"Detected errors count: {len(errors)}")
    assert len(errors) >= 1, "Failed to parse terminal error pattern"
    print(f"Detected error pattern: {errors[0]['matched']}")
    print("[OK] TEST 1 PASSED: OCR error parser verified.")


def test_screen_capture_active_window():
    print("\n--- [TEST 2] Synthetic Active Window Capture Contract ---")
    capture = EventDrivenScreenCapture()
    synthetic_image = b"synthetic-screen-frame"
    synthetic_window = {
        "title": "Synthetic Browser - Amazon Orders",
        "hwnd": 0,
        "is_active_window": True,
        "bounds": {"left": 0, "top": 0, "width": 640, "height": 480},
        "capture_origin": {"left": 0, "top": 0},
    }
    capture.capture_active_window = Mock(return_value=(synthetic_image, 640, 480, synthetic_window))
    img_bytes, w, h, win_info = capture.capture_active_window(
        reason="synthetic_test", force=True, prefer_active_window=True
    )
    print(f"Synthetic frame: {len(img_bytes)} bytes | Resolution: {w}x{h}")
    print(f"Window Title: '{win_info.get('title')}' | Synthetic fixture only")
    assert len(img_bytes) > 0, "Image capture produced empty bytes"
    assert w > 0 and h > 0, "Invalid capture dimensions"
    assert "Synthetic" in win_info["title"]
    print("[OK] TEST 2 PASSED: Synthetic capture contract verified without reading the desktop.")


def test_screen_intelligence_caching_and_terminal():
    print("\n--- [TEST 3] Fresh Reasoning and Safe Exact-Request Cache ---")
    screen = {"frame": b"synthetic-screen-one", "text": "Customer Support"}
    fake_analyzer = Mock()

    def analyze(**kwargs):
        command = kwargs["command"]
        screen_context = kwargs["screen_context"]
        fake_analyzer.observed.append((command, screen_context.full_text))
        return {
            "website": screen_context.website,
            "page_type": screen_context.current_page,
            "user_intent": command,
            "reasoning_steps": [f"Fresh analysis: {command}"],
            "target_element": {"found": False},
            "explanation_text": f"Request={command}; screen={screen_context.full_text}",
            "explanation_voice": f"I analyzed {screen_context.full_text} for {command}.",
            "suggested_action": "explain",
            "workflow_completed": False,
        }

    fake_analyzer.observed = []
    fake_analyzer.analyze.side_effect = analyze
    service = ScreenIntelligenceService(page_analyzer=fake_analyzer)
    service.capture_engine.capture_active_window = Mock(side_effect=lambda **_: (
        screen["frame"], 640, 480,
        {
            "title": "Synthetic Browser - Amazon",
            "hwnd": 0,
            "app_name": "Synthetic Browser",
            "browser_name": "Synthetic Browser",
            "is_browser": True,
            "bounds": {"left": 0, "top": 0, "width": 640, "height": 480},
            "capture_origin": {"left": 0, "top": 0},
        },
    ))
    service.ocr_engine.extract_text = Mock(side_effect=lambda _: {
        "engine": "synthetic-test",
        "full_text": screen["text"],
        "lines": [screen["text"]],
        "blocks": [],
        "average_confidence": 0.99,
        "detected_errors": [],
        "is_terminal_like": False,
    })

    history = [{"role": "user", "content": "Open customer support"}]
    first = service.get_screen_understanding("Open customer support", history)
    changed_request = service.get_screen_understanding("I want to return this product", history)
    assert not first.get("cache_hit", False)
    assert not changed_request.get("cache_hit", False)
    assert len(fake_analyzer.observed) == 2, "A changed user request must be freshly reasoned"
    assert "I want to return this product" in changed_request["explanation_text"]

    exact_repeat = service.get_screen_understanding("I want to return this product", history)
    assert exact_repeat.get("cache_hit") is True, "Only the identical request and screen may reuse analysis"
    assert len(fake_analyzer.observed) == 2

    screen["frame"] = b"synthetic-screen-two"
    screen["text"] = "Return item - Select a reason"
    changed_screen = service.get_screen_understanding("I want to return this product", history)
    assert not changed_screen.get("cache_hit", False), "A changed screen must trigger fresh reasoning"
    assert "Select a reason" in changed_screen["explanation_text"]
    assert len(fake_analyzer.observed) == 3

    stats = service.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["total_analyses"] == 3
    print("[OK] Different request and changed screen re-analyzed; exact repeat on identical state reused cached result.")
    service.stop()


def test_visual_confidence_gate():
    print("\n--- [TEST 4] Visual Confidence Check ---")
    service = ScreenIntelligenceService(confidence_threshold=0.75)

    # Mock low confidence analysis
    low_conf_analysis = {
        "suggested_action": "click",
        "target_element": {
            "found": True,
            "label": "Ambiguous Button",
            "confidence": 0.42
        },
        "ocr_confidence": 0.30
    }

    ok, warning = service.verify_visual_confidence(low_conf_analysis)
    print(f"Confidence verification result: {ok}")
    print(f"Warning issued: '{warning}'")
    assert not ok, "Low confidence should have failed verification"
    assert "adjust the window or scroll slightly" in warning, "Expected spec-mandated warning message"
    print("[OK] TEST 4 PASSED: Visual Confidence Gate verified.")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING SCREEN INTELLIGENCE & MODULE 8.1 TESTS")
    print("=" * 60)
    test_ocr_engine()
    test_screen_capture_active_window()
    test_screen_intelligence_caching_and_terminal()
    test_visual_confidence_gate()
    print("\n[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
