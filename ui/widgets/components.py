# ============================================================
#  INTENT PLATFORM — Reusable UI Widgets
# ============================================================

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGraphicsDropShadowEffect, QFrame, QSizePolicy
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, Property, QSize,
    Signal, QRect, QPoint, QTimer, QParallelAnimationGroup
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QLinearGradient,
    QBrush, QPen, QIcon
)
from intent_platform.ui.theme import Theme


# ============================================================
#  GlowButton — Premium gradient button with hover glow
# ============================================================

class GlowButton(QPushButton):
    """Gradient button with hover glow animation."""

    def __init__(self, text="", icon_text="", gradient=None, parent=None):
        super().__init__(text, parent)
        self._hover_opacity = 0.0
        self._icon_text = icon_text
        self._gradient_colors = gradient or (Theme.ACCENT_CYAN, Theme.ACCENT_PURPLE)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setFont(QFont("Segoe UI", 13, QFont.DemiBold))

        self._hover_anim = QPropertyAnimation(self, b"hover_opacity")
        self._hover_anim.setDuration(200)
        self._hover_anim.setEasingCurve(QEasingCurve.InOutQuad)

        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: white;
                border: none;
                border-radius: {Theme.RADIUS_MD}px;
                padding: 0 24px;
                font-weight: 600;
            }}
        """)

    def _get_hover_opacity(self):
        return self._hover_opacity

    def _set_hover_opacity(self, val):
        self._hover_opacity = val
        self.update()

    hover_opacity = Property(float, _get_hover_opacity, _set_hover_opacity)

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # Background gradient
        grad = QLinearGradient(0, 0, rect.width(), rect.height())
        c1 = QColor(self._gradient_colors[0])
        c2 = QColor(self._gradient_colors[1])
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)

        path = QPainterPath()
        path.addRoundedRect(0, 0, rect.width(), rect.height(),
                            Theme.RADIUS_MD, Theme.RADIUS_MD)
        p.fillPath(path, QBrush(grad))

        # Hover glow overlay
        if self._hover_opacity > 0.01:
            overlay = QColor(255, 255, 255, int(30 * self._hover_opacity))
            p.fillPath(path, QBrush(overlay))

        # Text
        p.setPen(QColor("white"))
        p.setFont(self.font())
        text_rect = rect.adjusted(0, 0, 0, 0)
        full_text = f"{self._icon_text}  {self.text()}" if self._icon_text else self.text()
        p.drawText(text_rect, Qt.AlignCenter, full_text)
        p.end()


# ============================================================
#  DashboardCard — Interactive card with icon, description, hover
# ============================================================

class DashboardCard(QWidget):
    """Premium interactive card for dashboard navigation."""
    clicked = Signal()

    def __init__(self, title="", description="", icon_text="",
                 gradient=None, button_text="Open", parent=None):
        super().__init__(parent)
        self._hover = False
        self._hover_opacity = 0.0
        self._title = title
        self._description = description
        self._icon_text = icon_text
        self._gradient = gradient or (Theme.ACCENT_CYAN, Theme.ACCENT_PURPLE)
        self._button_text = button_text
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._hover_anim = QPropertyAnimation(self, b"hover_opacity_prop")
        self._hover_anim.setDuration(250)
        self._hover_anim.setEasingCurve(QEasingCurve.InOutCubic)

    def _get_hover_opacity(self):
        return self._hover_opacity

    def _set_hover_opacity(self, val):
        self._hover_opacity = val
        self.update()

    hover_opacity_prop = Property(float, _get_hover_opacity, _set_hover_opacity)

    def enterEvent(self, event):
        self._hover = True
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(1.0)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_opacity)
        self._hover_anim.setEndValue(0.0)
        self._hover_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = Theme.RADIUS_LG

        # ── Card background ──
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, r, r)

        bg = QColor(Theme.BG_CARD)
        p.fillPath(path, QBrush(bg))

        # Hover border glow
        if self._hover_opacity > 0.01:
            pen_color = QColor(self._gradient[0])
            pen_color.setAlphaF(0.4 * self._hover_opacity)
            p.setPen(QPen(pen_color, 1.5))
            p.drawRoundedRect(1, 1, w - 2, h - 2, r, r)

            # Subtle top gradient strip
            strip = QLinearGradient(0, 0, w, 0)
            c1 = QColor(self._gradient[0])
            c2 = QColor(self._gradient[1])
            c1.setAlphaF(0.8 * self._hover_opacity)
            c2.setAlphaF(0.8 * self._hover_opacity)
            strip.setColorAt(0, c1)
            strip.setColorAt(1, c2)
            strip_path = QPainterPath()
            strip_path.addRoundedRect(0, 0, w, 4, 2, 2)
            p.fillPath(strip_path, QBrush(strip))
        else:
            p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
            p.drawRoundedRect(1, 1, w - 2, h - 2, r, r)

        # ── Icon circle ──
        icon_y = 36
        icon_size = 56
        icon_x = 28

        icon_grad = QLinearGradient(icon_x, icon_y, icon_x + icon_size, icon_y + icon_size)
        icon_grad.setColorAt(0, QColor(self._gradient[0]))
        icon_grad.setColorAt(1, QColor(self._gradient[1]))

        icon_path = QPainterPath()
        icon_path.addRoundedRect(icon_x, icon_y, icon_size, icon_size, 16, 16)
        p.fillPath(icon_path, QBrush(icon_grad))

        # Icon emoji
        p.setPen(QColor("white"))
        p.setFont(QFont("Segoe UI Emoji", 22))
        p.drawText(QRect(icon_x, icon_y, icon_size, icon_size), Qt.AlignCenter, self._icon_text)

        # ── Title ──
        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 17, QFont.Bold))
        p.drawText(QRect(28, icon_y + icon_size + 16, w - 56, 30), Qt.AlignLeft | Qt.AlignVCenter, self._title)

        # ── Description ──
        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 12))
        desc_rect = QRect(28, icon_y + icon_size + 48, w - 56, 40)
        p.drawText(desc_rect, Qt.AlignLeft | Qt.TextWordWrap, self._description)

        # ── Button strip at bottom ──
        btn_h = 40
        btn_y = h - btn_h - 20
        btn_w = 120
        btn_x = 28

        btn_path = QPainterPath()
        btn_path.addRoundedRect(btn_x, btn_y, btn_w, btn_h, 10, 10)

        if self._hover_opacity > 0.3:
            btn_grad = QLinearGradient(btn_x, btn_y, btn_x + btn_w, btn_y + btn_h)
            btn_grad.setColorAt(0, QColor(self._gradient[0]))
            btn_grad.setColorAt(1, QColor(self._gradient[1]))
            p.fillPath(btn_path, QBrush(btn_grad))
            p.setPen(QColor("white"))
        else:
            p.setPen(QPen(QColor(Theme.BORDER_HOVER), 1.5))
            p.drawPath(btn_path)
            p.setPen(QColor(Theme.TEXT_SECONDARY))

        p.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
        p.drawText(QRect(btn_x, btn_y, btn_w, btn_h), Qt.AlignCenter, self._button_text)

        p.end()


# ============================================================
#  SidebarNav — Navigation item for left sidebar
# ============================================================

class SidebarNavItem(QWidget):
    """Single navigation item in the sidebar."""
    clicked = Signal(str)

    def __init__(self, page_id="", icon_text="", label="", parent=None):
        super().__init__(parent)
        self._page_id = page_id
        self._icon = icon_text
        self._label = label
        self._active = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)

    def set_active(self, active):
        self._active = active
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._page_id)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        if self._active:
            # Active indicator bar
            bar = QPainterPath()
            bar.addRoundedRect(0, 6, 3, h - 12, 2, 2)
            p.fillPath(bar, QBrush(QColor(Theme.ACCENT_CYAN)))

            # Active background
            bg = QPainterPath()
            bg.addRoundedRect(8, 2, w - 16, h - 4, 8, 8)
            p.fillPath(bg, QBrush(QColor(Theme.ACCENT_CYAN + "15")))

            text_color = QColor(Theme.ACCENT_CYAN)
        elif self._hover:
            bg = QPainterPath()
            bg.addRoundedRect(8, 2, w - 16, h - 4, 8, 8)
            p.fillPath(bg, QBrush(QColor(255, 255, 255, 8)))
            text_color = QColor(Theme.TEXT_PRIMARY)
        else:
            text_color = QColor(Theme.TEXT_SECONDARY)

        # Icon
        p.setPen(text_color)
        p.setFont(QFont("Segoe UI Emoji", 15))
        p.drawText(QRect(20, 0, 36, h), Qt.AlignCenter, self._icon)

        # Label
        p.setFont(QFont("Segoe UI", 13))
        p.drawText(QRect(62, 0, w - 80, h), Qt.AlignLeft | Qt.AlignVCenter, self._label)

        p.end()


# ============================================================
#  StatusBadge — Small colored badge
# ============================================================

class StatusBadge(QWidget):
    """Colored status dot with label."""

    def __init__(self, text="Active", color=None, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color or Theme.ACCENT_GREEN
        self.setFixedHeight(24)
        self.setFixedWidth(max(70, len(text) * 9 + 28))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Background pill
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        bg = QColor(self._color)
        bg.setAlphaF(0.15)
        p.fillPath(path, QBrush(bg))

        # Dot
        p.setBrush(QBrush(QColor(self._color)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(8, 8, 8, 8)

        # Text
        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        p.drawText(QRect(22, 0, self.width() - 28, self.height()),
                   Qt.AlignLeft | Qt.AlignVCenter, self._text)
        p.end()


# ============================================================
#  SectionHeader — Section title with optional action
# ============================================================

class SectionHeader(QWidget):
    """Section title with subtitle."""

    def __init__(self, title="", subtitle="", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {Theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setFont(QFont("Segoe UI", 13))
            sub_lbl.setStyleSheet(f"color: {Theme.TEXT_SECONDARY}; background: transparent;")
            layout.addWidget(sub_lbl)


# ============================================================
#  StatCard — Small metric display card
# ============================================================

class StatCard(QWidget):
    """Small stat card showing a metric value."""

    def __init__(self, label="", value="", icon_text="", color=None, parent=None):
        super().__init__(parent)
        self._label = label
        self._value = value
        self._icon = icon_text
        self._color = color or Theme.ACCENT_CYAN
        self.setFixedHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Card bg
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, Theme.RADIUS_MD, Theme.RADIUS_MD)
        p.fillPath(path, QBrush(QColor(Theme.BG_CARD)))
        p.setPen(QPen(QColor(Theme.BORDER_SUBTLE), 1))
        p.drawRoundedRect(1, 1, w - 2, h - 2, Theme.RADIUS_MD, Theme.RADIUS_MD)

        # Icon
        p.setPen(QColor(self._color))
        p.setFont(QFont("Segoe UI Emoji", 20))
        p.drawText(QRect(16, 12, 40, 40), Qt.AlignCenter, self._icon)

        # Value
        p.setPen(QColor(Theme.TEXT_PRIMARY))
        p.setFont(QFont("Segoe UI", 20, QFont.Bold))
        p.drawText(QRect(64, 14, w - 80, 30), Qt.AlignLeft | Qt.AlignVCenter, self._value)

        # Label
        p.setPen(QColor(Theme.TEXT_SECONDARY))
        p.setFont(QFont("Segoe UI", 11))
        p.drawText(QRect(64, 48, w - 80, 24), Qt.AlignLeft | Qt.AlignVCenter, self._label)

        p.end()
