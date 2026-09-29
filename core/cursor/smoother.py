# ============================================================
#  VELOCITY-ADAPTIVE EXPONENTIAL SMOOTHER
#  Zero-jitter micro-movements + instantaneous macro-travel
# ============================================================

import math
from typing import Tuple, Optional

class VelocityAdaptiveSmoother:
    """Smooths screen coordinate streams adaptively using movement speed."""

    def __init__(
        self,
        slow_alpha: float = 0.35,
        fast_alpha: float = 0.92,
        vel_slow_thresh: float = 3.0,
        vel_fast_thresh: float = 25.0,
        dead_zone_px: float = 1.2
    ):
        self.slow_alpha = slow_alpha
        self.fast_alpha = fast_alpha
        self.vel_slow = vel_slow_thresh
        self.vel_fast = vel_fast_thresh
        self.dead_zone = dead_zone_px

        self.sx: Optional[float] = None
        self.sy: Optional[float] = None
        self.prev_raw_x: Optional[float] = None
        self.prev_raw_y: Optional[float] = None

    def reset(self):
        self.sx = None
        self.sy = None
        self.prev_raw_x = None
        self.prev_raw_y = None

    def update(self, raw_x: float, raw_y: float) -> Tuple[int, int]:
        if self.sx is None or self.sy is None:
            self.sx = float(raw_x)
            self.sy = float(raw_y)
            self.prev_raw_x = float(raw_x)
            self.prev_raw_y = float(raw_y)
            return int(self.sx), int(self.sy)

        # Raw displacement
        dx = raw_x - self.prev_raw_x
        dy = raw_y - self.prev_raw_y
        velocity = math.hypot(dx, dy)
        self.prev_raw_x = raw_x
        self.prev_raw_y = raw_y

        # Velocity interpolation for alpha
        if velocity <= self.vel_slow:
            alpha = self.slow_alpha
        elif velocity >= self.vel_fast:
            alpha = self.fast_alpha
        else:
            t = (velocity - self.vel_slow) / (self.vel_fast - self.vel_slow)
            alpha = self.slow_alpha + t * (self.fast_alpha - self.slow_alpha)

        # Exponential smoothing
        new_sx = alpha * raw_x + (1.0 - alpha) * self.sx
        new_sy = alpha * raw_y + (1.0 - alpha) * self.sy

        # Dead zone check against current smoothed position
        if math.hypot(new_sx - self.sx, new_sy - self.sy) >= self.dead_zone:
            self.sx = new_sx
            self.sy = new_sy

        return int(self.sx), int(self.sy)
