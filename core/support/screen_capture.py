# ============================================================
#  EVENT-DRIVEN SCREEN CAPTURE ENGINE — Privacy-Preserving
#  Captures screen ONLY on user demand, action requests, or
#  significant page changes. Uses mss for high performance.
# ============================================================

import io
import time
import sys
import ctypes
from typing import Tuple, Optional
from PIL import Image

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

# Ensure Windows DPI awareness is active for pixel-perfect coordinates
if sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class EventDrivenScreenCapture:
    """
    Event-driven screen capture engine.
    Ensures zero continuous streaming: captures only when user asks questions,
    requests actions, or when significant UI change occurs.
    """

    def __init__(self, change_threshold: float = 0.12):
        self.change_threshold = change_threshold
        self.last_capture_time = 0.0
        self.last_downsample: Optional[Image.Image] = None
        self.last_img_bytes: Optional[bytes] = None
        self.last_size: Tuple[int, int] = (1920, 1080)
        self.total_captures = 0

    def capture(self, reason: str = "user_request", force: bool = True) -> Tuple[bytes, int, int]:
        """
        Captures the primary monitor using mss.
        Returns: (png_bytes, width, height)
        """
        now = time.time()
        # Cooldown guard: prevent double-capturing within 300ms unless forced
        if not force and (now - self.last_capture_time < 0.30) and self.last_img_bytes:
            return self.last_img_bytes, self.last_size[0], self.last_size[1]

        pil_img = None
        w, h = 1920, 1080

        if MSS_AVAILABLE:
            try:
                with mss.mss() as sct:
                    # Capture primary monitor (monitors[1]) or all (monitors[0])
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    sct_img = sct.grab(monitor)
                    # Convert BGRA to RGB PIL Image
                    pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    w, h = sct_img.width, sct_img.height
            except Exception as e:
                print(f"[ScreenCapture] mss capture warning: {e}. Falling back to PIL...")
                pil_img = None

        if pil_img is None:
            # Fallback to PIL ImageGrab
            try:
                from PIL import ImageGrab
                pil_img = ImageGrab.grab(all_screens=False)
                w, h = pil_img.size
            except Exception:
                try:
                    import pyautogui
                    res_w, res_h = pyautogui.size()
                except Exception:
                    res_w, res_h = 1920, 1080
                pil_img = Image.new("RGB", (res_w, res_h), color=(30, 32, 40))
                w, h = res_w, res_h

        # Compress to PNG bytes in-memory (no disk writing for speed & privacy)
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG", optimize=True)
        img_bytes = buf.getvalue()

        # Update cache & downsampled thumbnail for change detection
        self.last_img_bytes = img_bytes
        self.last_size = (w, h)
        self.last_capture_time = now
        self.total_captures += 1

        try:
            self.last_downsample = pil_img.resize((64, 64)).convert("L")
        except Exception:
            self.last_downsample = None

        print(f"[ScreenCapture] Captured frame for reason='{reason}' (#{self.total_captures}, res={w}x{h})")
        return img_bytes, w, h

    def has_screen_changed_significantly(self) -> bool:
        """
        Compares a fast downsampled screenshot against the last saved frame
        to check if the webpage or window updated significantly (e.g. page transition, modal popup).
        """
        if self.last_downsample is None:
            return True

        try:
            from PIL import ImageGrab, ImageChops
            current = ImageGrab.grab(all_screens=False).resize((64, 64)).convert("L")
            diff = ImageChops.difference(current, self.last_downsample)
            stat = diff.getextrema()
            # If max difference or average variance exceeds threshold
            hist = diff.histogram()
            diff_pixels = sum(hist[16:])  # Count pixels that shifted noticeably
            ratio = diff_pixels / (64 * 64)
            return ratio >= self.change_threshold
        except Exception:
            return True
