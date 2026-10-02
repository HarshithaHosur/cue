# ============================================================
#  HIGH-PRECISION SCREEN CAPTURE ENGINE — Privacy-Preserving
#  Captures screen or active window ONLY on user demand or UI change.
#  Uses high-performance mss with active window bounding box support.
# ============================================================

import io
import time
import sys
import ctypes
import os
from typing import Tuple, Optional, Dict, Any
from PIL import Image

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import win32gui
    import win32process
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    import pygetwindow as gw
    GW_AVAILABLE = True
except ImportError:
    GW_AVAILABLE = False

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
    High-precision event-driven screen capture engine.
    Ensures zero continuous streaming: captures only when user asks questions,
    requests actions, or when significant UI change occurs.
    Supports capturing only the active window whenever possible.
    """

    def __init__(self, change_threshold: float = 0.12):
        self.change_threshold = change_threshold
        self.last_capture_time = 0.0
        self.last_downsample: Optional[Image.Image] = None
        self.last_img_bytes: Optional[bytes] = None
        self.last_size: Tuple[int, int] = (1920, 1080)
        self.last_window_info: Dict[str, Any] = {}
        self.total_captures = 0

    def capture(self, reason: str = "user_request", force: bool = True) -> Tuple[bytes, int, int]:
        """
        Captures the primary monitor using mss.
        Returns: (png_bytes, width, height)
        """
        img_bytes, w, h, _ = self.capture_active_window(reason=reason, force=force, prefer_active_window=False)
        return img_bytes, w, h

    def capture_active_window(
        self,
        reason: str = "user_request",
        force: bool = True,
        prefer_active_window: bool = True
    ) -> Tuple[bytes, int, int, Dict[str, Any]]:
        """
        High-precision screen capture.
        When prefer_active_window is True, detects the foreground window (Browser, VS Code,
        Terminal, Installer, Dialog) and captures its exact bounding box.
        If active window cannot be isolated or is minimized, captures the primary monitor.
        Returns: (png_bytes, width, height, window_info)
        """
        now = time.time()
        # Cooldown guard: prevent double-capturing within 300ms unless forced
        if not force and (now - self.last_capture_time < 0.30) and self.last_img_bytes:
            return self.last_img_bytes, self.last_size[0], self.last_size[1], self.last_window_info

        pil_img = None
        w, h = 1920, 1080
        active_rect = None
        capture_origin = {"left": 0, "top": 0}
        window_title = "Desktop"
        window_hwnd = 0
        is_active_window = False

        # ── 1. Query Active Window Rect if requested ──
        if prefer_active_window and WIN32_AVAILABLE and sys.platform == 'win32':
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    _, foreground_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if foreground_pid == os.getpid():
                        candidates = []

                        def collect_external_window(candidate_hwnd, _):
                            if not win32gui.IsWindowVisible(candidate_hwnd) or win32gui.IsIconic(candidate_hwnd):
                                return True
                            _, candidate_pid = win32process.GetWindowThreadProcessId(candidate_hwnd)
                            title = win32gui.GetWindowText(candidate_hwnd).strip()
                            if candidate_pid != os.getpid() and title:
                                candidates.append((candidate_hwnd, title))
                            return True

                        win32gui.EnumWindows(collect_external_window, None)
                        if candidates:
                            hwnd = candidates[0][0]
                if hwnd and win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
                    window_hwnd = hwnd
                    window_title = win32gui.GetWindowText(hwnd).strip()
                    rect = win32gui.GetWindowRect(hwnd)  # (left, top, right, bottom)
                    rw = rect[2] - rect[0]
                    rh = rect[3] - rect[1]
                    # Sanity check: valid non-minimized window of reasonable size
                    if rw >= 120 and rh >= 120 and rect[0] >= -500 and rect[1] >= -500:
                        active_rect = {
                            "left": rect[0],
                            "top": rect[1],
                            "width": rw,
                            "height": rh,
                        }
                        is_active_window = True
            except Exception as e:
                print(f"[ScreenCapture] win32 active window check note: {e}")

        # ── 2. Capture via mss ──
        if MSS_AVAILABLE:
            try:
                with mss.mss() as sct:
                    primary_monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]

                    if is_active_window and active_rect:
                        left = max(primary_monitor["left"], active_rect["left"])
                        top = max(primary_monitor["top"], active_rect["top"])
                        target_rect = {
                            "left": left,
                            "top": top,
                            "width": min(
                                primary_monitor["left"] + primary_monitor["width"] - left,
                                active_rect["left"] + active_rect["width"] - left,
                            ),
                            "height": min(
                                primary_monitor["top"] + primary_monitor["height"] - top,
                                active_rect["top"] + active_rect["height"] - top,
                            ),
                        }
                        capture_origin = {"left": target_rect["left"], "top": target_rect["top"]}
                        sct_img = sct.grab(target_rect)
                    else:
                        sct_img = sct.grab(primary_monitor)

                    pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    w, h = sct_img.width, sct_img.height
            except Exception as e:
                print(f"[ScreenCapture] mss capture warning: {e}. Falling back to PIL...")
                pil_img = None

        # ── 3. Fallback to PIL ImageGrab ──
        if pil_img is None:
            try:
                from PIL import ImageGrab
                if is_active_window and active_rect:
                    capture_origin = {"left": active_rect["left"], "top": active_rect["top"]}
                    bbox = (
                        active_rect["left"],
                        active_rect["top"],
                        active_rect["left"] + active_rect["width"],
                        active_rect["top"] + active_rect["height"]
                    )
                    pil_img = ImageGrab.grab(bbox=bbox)
                else:
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

        # Compress to PNG bytes in-memory
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG", optimize=True)
        img_bytes = buf.getvalue()

        window_info = {
            "title": window_title,
            "hwnd": window_hwnd,
            "is_active_window": is_active_window,
            "bounds": active_rect or {"left": 0, "top": 0, "width": w, "height": h},
            "capture_origin": capture_origin,
            "timestamp": now,
            "reason": reason
        }

        # Update cache & downsampled thumbnail for change detection
        self.last_img_bytes = img_bytes
        self.last_size = (w, h)
        self.last_window_info = window_info
        self.last_capture_time = now
        self.total_captures += 1

        try:
            self.last_downsample = pil_img.resize((64, 64)).convert("L")
        except Exception:
            self.last_downsample = None

        target_desc = f"active window '{window_title}'" if is_active_window else "full primary screen"
        print(f"[ScreenCapture] Captured {target_desc} for reason='{reason}' (#{self.total_captures}, res={w}x{h})")
        return img_bytes, w, h, window_info

    def has_screen_changed_significantly(self) -> bool:
        """
        Compares a fast downsampled screenshot against the last saved frame
        to check if the webpage or window updated significantly (e.g. page transition, modal popup).
        """
        if self.last_downsample is None:
            return True

        current_downsample = None

        # 1. Try mss first for fast downsampled capture
        if MSS_AVAILABLE:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    sct_img = sct.grab(monitor)
                    pil_img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    current_downsample = pil_img.resize((64, 64)).convert("L")
            except Exception:
                current_downsample = None

        # 2. Try PIL ImageGrab fallback
        if current_downsample is None:
            try:
                from PIL import ImageGrab
                current_downsample = ImageGrab.grab(all_screens=False).resize((64, 64)).convert("L")
            except Exception:
                current_downsample = None

        # If both capture mechanisms failed (e.g. headless session), assume screen hasn't changed
        if current_downsample is None:
            return False

        try:
            from PIL import ImageChops
            diff = ImageChops.difference(current_downsample, self.last_downsample)
            hist = diff.histogram()
            diff_pixels = sum(hist[16:])  # Count pixels that shifted noticeably
            ratio = diff_pixels / (64 * 64)
            return ratio >= self.change_threshold
        except Exception:
            return False
