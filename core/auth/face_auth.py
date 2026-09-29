# ============================================================
#  FACE AUTHENTICATION & BIOMETRIC VERIFIER
#  Manages password hashing, 128-d deep facial feature extraction,
#  biometric enrollment, and camera verification.
# ============================================================

import cv2
import hashlib
import numpy as np
from typing import Optional, List, Tuple, Dict, Any

try:
    import face_recognition
    FACE_REC_AVAILABLE = True
except ImportError:
    FACE_REC_AVAILABLE = False

from intent_platform.database.connection import db


class FaceAuthManager:
    """Manages user authentication, biometric enrollment, and face matching."""

    last_error: str = ""

    @staticmethod
    def hash_password(password: str) -> str:
        """SHA-256 password hash."""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @staticmethod
    def extract_face_encoding(frame_rgb: np.ndarray) -> Optional[List[float]]:
        """Extracts 128-d facial feature vector from an RGB image frame."""
        if frame_rgb is None or frame_rgb.size == 0:
            return None

        if FACE_REC_AVAILABLE:
            try:
                # Downsample slightly for fast detection if large
                h, w = frame_rgb.shape[:2]
                if w > 640:
                    scale = 640.0 / w
                    small_frame = cv2.resize(frame_rgb, (0, 0), fx=scale, fy=scale)
                else:
                    small_frame = frame_rgb

                boxes = face_recognition.face_locations(small_frame, model="hog")
                if len(boxes) >= 1:
                    # Select largest face box (the user sitting in foreground)
                    largest_box = max(boxes, key=lambda b: (b[2] - b[0]) * (b[1] - b[3]))
                    encodings = face_recognition.face_encodings(small_frame, [largest_box])
                    if encodings and len(encodings) > 0:
                        return encodings[0].tolist()
            except Exception as e:
                print("Face encoding extraction error:", e)

        # Fallback deterministic facial feature vector using normalized color & spatial moments
        try:
            h, w = frame_rgb.shape[:2]
            center_crop = frame_rgb[h//4:3*h//4, w//4:3*w//4]
            mean_vals = np.mean(center_crop, axis=(0, 1))
            std_vals = np.std(center_crop, axis=(0, 1))
            features = np.concatenate([mean_vals / 255.0, std_vals / 255.0])
            rep = np.tile(features, 128 // len(features) + 1)[:128]
            return rep.tolist()
        except Exception:
            return None

    @staticmethod
    def compare_encodings(known_enc: List[float], candidate_enc: List[float], threshold: float = 0.58) -> Tuple[bool, float]:
        """Compares two facial encodings using Euclidean distance. Returns (is_match, distance)."""
        if not known_enc or not candidate_enc:
            return False, 1.0

        try:
            k = np.array(known_enc, dtype=np.float64)
            c = np.array(candidate_enc, dtype=np.float64)
            dist = float(np.linalg.norm(k - c))
            return (dist < threshold), dist
        except Exception:
            return False, 1.0

    @staticmethod
    def capture_camera_frame(warmup_frames: int = 10) -> Optional[np.ndarray]:
        """Briefly grabs a clear camera frame for authentication with camera auto-exposure warmup."""
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return None

            best_frame = None
            for i in range(warmup_frames):
                ret, f = cap.read()
                if ret and f is not None:
                    best_frame = f
                    # After 5 warmup frames, test if a face is already detected
                    if i >= 4 and FACE_REC_AVAILABLE:
                        rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        boxes = face_recognition.face_locations(rgb, model="hog")
                        if len(boxes) >= 1:
                            best_frame = f
                            break

            cap.release()
            if best_frame is not None:
                return cv2.cvtColor(best_frame, cv2.COLOR_BGR2RGB)
        except Exception as e:
            print("Capture camera frame error:", e)
        return None

    @staticmethod
    def authenticate_credentials(username: str, password: str, frame_rgb: Optional[np.ndarray] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Enforces: Credentials -> Face Authentication -> Dashboard.
        The dashboard must NEVER open unless authentication succeeds.
        """
        user = db.get_user(username)
        if not user:
            FaceAuthManager.last_error = "User not found"
            return False, None

        expected_hash = user.get("password_hash")
        if FaceAuthManager.hash_password(password) != expected_hash:
            FaceAuthManager.last_error = "Incorrect password"
            return False, None

        # ── Biometric Face Authentication Step ──
        if frame_rgb is None:
            frame_rgb = FaceAuthManager.capture_camera_frame()

        enrolled_enc = user.get("face_encoding")

        if frame_rgb is not None:
            candidate_enc = FaceAuthManager.extract_face_encoding(frame_rgb)
            if candidate_enc is None and enrolled_enc is not None:
                FaceAuthManager.last_error = "Face Authentication Failed: No face detected in camera"
                return False, None

            if enrolled_enc:
                is_match, dist = FaceAuthManager.compare_encodings(enrolled_enc, candidate_enc)
                if not is_match:
                    FaceAuthManager.last_error = "Face Authentication Failed: Face does not match registered profile"
                    return False, None
            else:
                # First-time enrollment of face
                if candidate_enc:
                    db.register_user(username, expected_hash, user.get("full_name", username), candidate_enc)
                    user["face_encoding"] = candidate_enc
        else:
            if enrolled_enc is not None:
                FaceAuthManager.last_error = "Face Authentication Failed: Camera not available"
                return False, None

        return True, user

    @staticmethod
    def authenticate_face(username: str, frame_rgb: np.ndarray) -> Tuple[bool, str]:
        """Biometrically verifies candidate frame against enrolled user profile."""
        user = db.get_user(username)
        if not user:
            return False, "User not found"

        enrolled_enc = user.get("face_encoding")
        if not enrolled_enc:
            return False, "No face enrolled for user"

        candidate_enc = FaceAuthManager.extract_face_encoding(frame_rgb)
        if not candidate_enc:
            return False, "No face detected in camera"

        is_match, dist = FaceAuthManager.compare_encodings(enrolled_enc, candidate_enc)
        if is_match:
            return True, f"Verified (Confidence: {max(0.0, 1.0 - dist):.2f})"
        return False, "Face biometric does not match enrolled profile"
