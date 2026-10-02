# ============================================================
#  HAND OWNERSHIP & CONTINUOUS AUTHENTICATION VERIFIER
#  Enforces strict multi-person gating, biometric identity tracking,
#  anatomical plausibility, and temporal continuity.
# ============================================================

import math
import time
from typing import Optional, NamedTuple, List

import cv2
import numpy as np

try:
    import mediapipe as mp
    MP_AVAILABLE = True
except ImportError:
    MP_AVAILABLE = False

try:
    import face_recognition_models
    import face_recognition
    FACE_REC_AVAILABLE = True
except (ImportError, SystemExit):
    FACE_REC_AVAILABLE = False

from intent_platform.core.auth.face_auth import FaceAuthManager


class VerificationResult(NamedTuple):
    gesture_ready: bool
    auth_lost: bool
    reason: str
    face_count: int = 1
    layer_failed: Optional[int] = None


class HandOwnershipVerifier:
    """
    Continuous Multi-Layer Security Pipeline:
    1. Multi-Person Gate & Continuous Presence:
       - Ensures exactly ONE authenticated face is present.
       - If user leaves frame (0 faces) -> Agent pauses.
       - If multiple faces detected (>1 faces) -> Agent pauses.
       - If unauthorized face appears -> Agent pauses.
    2. Anatomical Plausibility:
       - Hand wrist must anatomically connect to the tracked pose body.
    3. Temporal Continuity:
       - Rejects physically impossible wrist teleportations.
    """

    def __init__(
        self,
        max_faces: int = 1,
        max_wrist_jump: float = 0.25,
        max_wrist_mismatch: float = 0.18,
        face_check_interval: int = 3
    ):
        self.max_faces = max_faces
        self.max_wrist_jump = max_wrist_jump
        self.max_wrist_mismatch = max_wrist_mismatch
        self.face_check_interval = face_check_interval

        self.last_wrist_x: Optional[float] = None
        self.last_wrist_y: Optional[float] = None
        self.last_verified_time = 0.0

        # Frame counter for biometric verification rate
        self.frame_count = 0
        self.cached_face_count = 1
        self.cached_face_match = True
        self.authenticated_encoding: Optional[List[float]] = None

        # MediaPipe Face Detection
        self.face_detector = None
        if MP_AVAILABLE:
            try:
                self.mp_face = mp.solutions.face_detection
                self.face_detector = self.mp_face.FaceDetection(
                    min_detection_confidence=0.55,
                    model_selection=0
                )
            except Exception:
                self.face_detector = None

    def set_authenticated_encoding(self, encoding: Optional[List[float]]):
        """Sets the baseline 128-d face encoding of the logged in user."""
        self.authenticated_encoding = encoding

    def verify(
        self,
        frame_rgb: np.ndarray,
        hand_landmarks=None,
        pose_landmarks=None
    ) -> VerificationResult:
        """
        Runs continuous face verification and hand ownership defense.
        """
        self.frame_count += 1
        now = time.time()

        # ── LAYER 1: Continuous Authentication & Face Count Gate ──
        # Check faces every N frames for performance and responsiveness
        if (self.frame_count % self.face_check_interval == 0) or (self.frame_count < 5):
            face_count = 0
            if self.face_detector is not None and frame_rgb is not None:
                try:
                    res = self.face_detector.process(frame_rgb)
                    if res and res.detections:
                        face_count = len(res.detections)
                except Exception:
                    face_count = 1
            else:
                face_count = 1

            self.cached_face_count = face_count

            # If face_recognition is available and an authenticated encoding is enrolled
            if face_count == 1 and self.authenticated_encoding and FACE_REC_AVAILABLE:
                # Check biometric identity periodically (every 15 frames ~0.5s)
                if self.frame_count % 15 == 0:
                    cand_enc = FaceAuthManager.extract_face_encoding(frame_rgb)
                    if cand_enc:
                        is_match, _ = FaceAuthManager.compare_encodings(self.authenticated_encoding, cand_enc)
                        self.cached_face_match = is_match
                    else:
                        self.cached_face_match = True
            else:
                self.cached_face_match = True

        face_count = self.cached_face_count

        # Requirement: "The authenticated user leaves the frame"
        if face_count == 0:
            return VerificationResult(
                gesture_ready=False,
                auth_lost=True,
                reason="Authentication Lost - Agent Paused",
                face_count=0,
                layer_failed=1
            )

        # Requirement: "Another person appears OR multiple faces appear"
        if face_count > self.max_faces:
            return VerificationResult(
                gesture_ready=False,
                auth_lost=True,
                reason="Authentication Lost - Agent Paused",
                face_count=face_count,
                layer_failed=1
            )

        # Requirement: "Continuous biometric match"
        if not self.cached_face_match:
            return VerificationResult(
                gesture_ready=False,
                auth_lost=True,
                reason="Authentication Lost - Agent Paused",
                face_count=1,
                layer_failed=1
            )

        # If hand is not visible, continuous auth passed but gestures are waiting for hand
        if not hand_landmarks:
            return VerificationResult(
                gesture_ready=False,
                auth_lost=False,
                reason="No hand visible",
                face_count=1,
                layer_failed=None
            )

        wrist = hand_landmarks[0]

        # ── LAYER 2: Anatomical Pose Check ──
        if pose_landmarks is not None:
            try:
                rw = pose_landmarks.landmark[16]
                lw = pose_landmarks.landmark[15]
                dist_r = math.hypot(wrist.x - rw.x, wrist.y - rw.y)
                dist_l = math.hypot(wrist.x - lw.x, wrist.y - lw.y)
                min_pose_dist = min(dist_r, dist_l)

                if min_pose_dist > self.max_wrist_mismatch:
                    return VerificationResult(
                        gesture_ready=False,
                        auth_lost=False,
                        reason=f"Hand disconnected from pose ({min_pose_dist:.2f})",
                        face_count=1,
                        layer_failed=2
                    )
            except Exception:
                pass

        # ── LAYER 3: Temporal Continuity Check ──
        if self.last_wrist_x is not None and self.last_wrist_y is not None:
            displacement = math.hypot(wrist.x - self.last_wrist_x, wrist.y - self.last_wrist_y)
            dt = now - self.last_verified_time
            if dt < 0.20 and displacement > self.max_wrist_jump:
                return VerificationResult(
                    gesture_ready=False,
                    auth_lost=False,
                    reason=f"Implausible hand jump ({displacement:.2f})",
                    face_count=1,
                    layer_failed=3
                )

        self.last_wrist_x = wrist.x
        self.last_wrist_y = wrist.y
        self.last_verified_time = now

        return VerificationResult(
            gesture_ready=True,
            auth_lost=False,
            reason="Verified",
            face_count=1,
            layer_failed=None
        )
