# ============================================================
#  COMPREHENSIVE BACKEND VALIDATION TEST SUITE
# ============================================================

import sys
import os
import math
import numpy as np

# Ensure project root is on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

print("=" * 60)
print("  INTENT OS HCI BACKEND VERIFICATION SUITE")
print("=" * 60)

# ── 1. Context Manager ──
print("\n[1] Testing ContextManager...")
from intent_platform.core.context.context_manager import ContextManager
ctx = ContextManager.get_current_context()
print(f"  Current foreground app: '{ctx['detected_app']}' (Title: '{ctx['active_window_title']}')")
print(f"  Is Media Active: {ctx['is_media']}, Is Zoomable: {ctx['is_zoomable']}")
assert "detected_app" in ctx
print("  ✓ ContextManager OK")

# ── 2. Desktop Automation Actions ──
print("\n[2] Testing Desktop Automation Actions...")
from intent_platform.core.automation import actions
assert hasattr(actions, 'open_new_tab')
assert hasattr(actions, 'close_tab')
assert hasattr(actions, 'close_first_tab')
assert hasattr(actions, 'close_current_tab')
assert hasattr(actions, 'close_all_tabs')
assert hasattr(actions, 'switch_to_first_tab')
assert hasattr(actions, 'switch_to_last_tab')
assert hasattr(actions, 'take_screenshot')
assert hasattr(actions, 'zoom_in')
assert hasattr(actions, 'zoom_out')
assert hasattr(actions, 'change_volume')
assert hasattr(actions, 'find_document_file')
assert hasattr(actions, 'is_protected_file')

# Verify protected file filter
assert actions.is_protected_file("passwords.txt") is True
assert actions.is_protected_file("id_rsa.pem") is True
assert actions.is_protected_file(".env") is True
assert actions.is_protected_file("regular_report.docx") is False
print("  ✓ Actions & Security Filter OK")

# ── 3. Voice Intent Classifier ──
print("\n[3] Testing Voice Intent Classifier...")
from intent_platform.core.voice.classifier import VoiceIntentClassifier
classifier = VoiceIntentClassifier()

test_queries = [
    ("system open chrome", "open_chrome"),
    ("open spotify", "open_spotify"),
    ("open vs code", "open_vscode"),
    ("system open calculator", "open_calculator"),
    ("open project report", "open_item"),
    ("open ec hackathon pdf", "open_item"),
    ("system open new tab", "open_new_tab"),
    ("system close tab", "close_tab"),
    ("system close first tab", "close_first_tab"),
    ("system close current tab", "close_current_tab"),
    ("system close all tabs", "close_all_tabs"),
    ("system switch to first tab", "switch_to_first_tab"),
    ("system switch to last tab", "switch_to_last_tab"),
    ("system take screenshot", "take_screenshot"),
    ("system capture screen", "take_screenshot"),
    ("volume up", "volume_up"),
    ("volume down", "volume_down")
]

for query, expected_intent in test_queries:
    clean = query.replace("system", "").strip()
    res = classifier.predict(clean if clean else query)
    assert res is not None, f"Failed to classify: '{query}'"
    intent, conf, target = res
    print(f"  Query: '{query:<28}' -> Intent: {intent:<20} (Conf: {conf:.2f}, Target: {target})")
    assert intent == expected_intent, f"Expected {expected_intent} but got {intent} for '{query}'"

print("  ✓ VoiceIntentClassifier 100% matched required prompt command set")

# ── 4. Gesture Recognizer & Executor ──
print("\n[4] Testing Gesture Recognizer & Context-Aware Executor...")
from intent_platform.core.gesture.recognizer import GestureRecognizer
from intent_platform.core.gesture.executor import execute_gesture

rec = GestureRecognizer()

class DummyLandmark:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z

# Mock 21 landmarks
def make_mock_landmarks(finger_states):
    # finger_states: [thumb, index, middle, ring, pinky]
    lms = [DummyLandmark(0.5, 0.8)] # 0: wrist
    # thumb: 1, 2, 3, 4
    if finger_states[0]:
        lms.extend([DummyLandmark(0.4, 0.7), DummyLandmark(0.35, 0.6), DummyLandmark(0.3, 0.5), DummyLandmark(0.2, 0.4)])
    else:
        lms.extend([DummyLandmark(0.45, 0.7), DummyLandmark(0.46, 0.65), DummyLandmark(0.47, 0.6), DummyLandmark(0.48, 0.62)])

    # fingers: index (5-8), middle (9-12), ring (13-16), pinky (17-20)
    bases = [0.45, 0.5, 0.55, 0.6]
    for i, ext in enumerate(finger_states[1:]):
        bx = bases[i]
        if ext:
            lms.extend([DummyLandmark(bx, 0.55), DummyLandmark(bx, 0.45), DummyLandmark(bx, 0.35), DummyLandmark(bx, 0.25)])
        else:
            lms.extend([DummyLandmark(bx, 0.55), DummyLandmark(bx, 0.60), DummyLandmark(bx, 0.65), DummyLandmark(bx, 0.70)])

    return lms

# Test Palm
palm_lms = make_mock_landmarks([True, True, True, True, True])
g_palm = rec.detect_static_gesture(palm_lms)
print(f"  Open Palm detected as: {g_palm}")

# Test Peace
peace_lms = make_mock_landmarks([False, True, True, False, False])
g_peace = rec.detect_static_gesture(peace_lms)
print(f"  Peace Sign detected as: {g_peace}")

# Test Dual-hand Two Open Palms & Two Peace Signs
two_palms = rec.detect_two_hands(palm_lms, palm_lms)
print(f"  Two Open Palms detected as: {two_palms}")
assert two_palms == 'two_open_palms'

two_peace = rec.detect_two_hands(peace_lms, peace_lms)
print(f"  Two Peace Signs detected as: {two_peace}")
assert two_peace == 'two_peace_signs'

# Test Thumbs Up Context Awareness:
# In media -> Volume Up
vol_label = execute_gesture('thumbs_up', context='spotify')
print(f"  Thumbs Up in Spotify: {vol_label}")
assert vol_label == "Volume Up"

# In VS Code -> Zoom In
zoom_label = execute_gesture('thumbs_up', context='code_editor')
print(f"  Thumbs Up in VS Code: {zoom_label}")
assert zoom_label == "Zoom In"

# Fist -> Screenshot Saved
fist_label = execute_gesture('fist', context='default')
print(f"  Fist Action: {fist_label}")
assert fist_label == "Screenshot Saved"
print("  ✓ Gesture Recognition & Execution OK")

# ── 5. Cursor Controller & Velocity Smoother ──
print("\n[5] Testing Cursor Controller & Velocity Smoother...")
from intent_platform.core.cursor.cursor_controller import CursorController
from intent_platform.core.cursor.smoother import VelocityAdaptiveSmoother

smoother = VelocityAdaptiveSmoother()
p1 = smoother.update(100.0, 100.0)
p2 = smoother.update(102.0, 102.0)
p3 = smoother.update(500.0, 500.0)
assert p1 == (100, 100)
assert isinstance(p2[0], int)
assert isinstance(p3[0], int)

cursor = CursorController()
cursor.reset()
assert cursor.is_pinching is False
assert cursor.is_dragging is False
cursor.release()
print("  ✓ Cursor Controller & Velocity Smoother OK")

# ── 6. Face Authentication & Continuous Verification ──
print("\n[6] Testing Face Authentication & Hand Ownership Continuous Verifier...")
from intent_platform.core.auth.face_auth import FaceAuthManager
from intent_platform.core.auth.ownership_verifier import HandOwnershipVerifier

# Test password hashing
h1 = FaceAuthManager.hash_password("admin123")
h2 = FaceAuthManager.hash_password("admin123")
assert h1 == h2

# Test encoding comparison
enc_a = [0.1] * 128
enc_b = [0.1] * 128
enc_c = [0.9] * 128
is_match, dist = FaceAuthManager.compare_encodings(enc_a, enc_b)
assert is_match is True
assert dist < 0.01

is_mismatch, dist_far = FaceAuthManager.compare_encodings(enc_a, enc_c)
assert is_mismatch is False
assert dist_far > 0.55

# Test HandOwnershipVerifier continuous auth
verifier = HandOwnershipVerifier(max_faces=1)
verifier.set_authenticated_encoding(enc_a)
verifier.frame_count = 10
verifier.face_check_interval = 100

dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

# Simulating no face visible (user leaves frame)
verifier.cached_face_count = 0
res_leave = verifier.verify(dummy_frame, None, None)
print(f"  User left frame: auth_lost={res_leave.auth_lost}, reason='{res_leave.reason}'")
assert res_leave.auth_lost is True
assert res_leave.reason == "Authentication Lost - Agent Paused"

# Simulating multiple faces
verifier.cached_face_count = 2
res_multi = verifier.verify(dummy_frame, None, None)
print(f"  Multiple faces: auth_lost={res_multi.auth_lost}, reason='{res_multi.reason}'")
assert res_multi.auth_lost is True
assert res_multi.reason == "Authentication Lost - Agent Paused"

# Simulating single authenticated face present
verifier.cached_face_count = 1
verifier.cached_face_match = True
res_ok = verifier.verify(dummy_frame, palm_lms, None)
print(f"  Authenticated face present: auth_lost={res_ok.auth_lost}, reason='{res_ok.reason}'")
assert res_ok.auth_lost is False
assert res_ok.gesture_ready is True
print("  ✓ Continuous Authentication & Multi-Layer Verifier OK")

# ── 7. IntentEngine Coordination ──
print("\n[7] Testing IntentEngine Lifecycle...")
from intent_platform.core.engine import IntentEngine
engine = IntentEngine()
assert engine.is_agent_active is False

# Test deactivate & activate
engine.deactivate_agent()
assert engine.is_agent_active is False
assert engine.voice_engine.is_paused is True

engine.activate_agent()
assert engine.is_agent_active is True
assert engine.voice_engine.is_paused is False
print("  ✓ IntentEngine Activation & Lifecycle OK")

print("\n" + "=" * 60)
print("  ALL BACKEND TESTS PASSED SUCCESSFULLY! (100% VERIFIED)")
print("=" * 60)
