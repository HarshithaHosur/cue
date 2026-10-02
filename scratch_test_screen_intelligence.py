# ============================================================
#  VERIFICATION TEST: MODULE 8.1 & SCREEN INTELLIGENCE SERVICE
#  Tests high-precision screen capture, OCR engine, terminal
#  understanding, deduplication caching, and visual confidence.
# ============================================================

import sys
import os
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    print("\n--- [TEST 2] Active Window Screen Capture ---")
    capture = EventDrivenScreenCapture()
    img_bytes, w, h, win_info = capture.capture_active_window(
        reason="test_active_window",
        force=True,
        prefer_active_window=True
    )
    print(f"Captured {len(img_bytes)} bytes | Resolution: {w}x{h}")
    print(f"Window Title: '{win_info.get('title')}' | Active Window Isolated: {win_info.get('is_active_window')}")
    assert len(img_bytes) > 0, "Image capture produced empty bytes"
    assert w > 0 and h > 0, "Invalid capture dimensions"
    print("[OK] TEST 2 PASSED: Active window capture verified.")


def test_screen_intelligence_caching_and_terminal():
    print("\n--- [TEST 3] Screen Intelligence Deduplication & Terminal Diagnostic ---")
    service = ScreenIntelligenceService()
    service.start()
    time.sleep(0.6)  # Allow background monitor thread to register initial state

    # 1. Query Terminal Error Explanation
    print("\nExecuting Terminal Error Explanation Query...")
    analysis1 = service.get_screen_understanding(command="System explain this terminal error")
    print(f"Website/App: {analysis1.get('website')}")
    print(f"Explanation Voice: {analysis1.get('explanation_voice')}")
    print(f"Explanation Text: {analysis1.get('explanation_text')}")
    print(f"Cache Hit (First Call): {analysis1.get('cache_hit', False)}")
    assert not analysis1.get("cache_hit", False), "First call should be a cache miss"

    # 2. Query Follow-up (Should hit cache instantly)
    print("\nExecuting Follow-up Query (Expecting Cache Hit)...")
    analysis2 = service.get_screen_understanding(command="Can you explain more?")
    print(f"Cache Hit (Second Call): {analysis2.get('cache_hit', False)}")
    assert analysis2.get("cache_hit", False) is True, "Second call should hit the cache!"

    # 3. Check Performance Stats
    stats = service.get_stats()
    print(f"\nScreen Intelligence Stats: {stats}")
    assert stats["cache_hits"] >= 1, "Cache hit count not recorded"
    assert stats["api_calls_avoided"] >= 1, "API calls avoided not recorded"

    service.stop()
    print("[OK] TEST 3 PASSED: Screen Intelligence Deduplication & Terminal Diagnostic verified.")


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
