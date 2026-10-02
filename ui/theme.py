# ============================================================
#  INTENT PLATFORM — Premium Dark Theme System
# ============================================================


class Theme:
    """Centralized design tokens for the entire application."""

    # ── Color Palette ──
    BG_DARKEST = "#0a0b10"
    BG_DARKER = "#0f1117"
    BG_DARK = "#151721"
    BG_CARD = "#1a1d2e"
    BG_CARD_HOVER = "#1f2337"
    BG_HOVER = "#1f2337"
    BG_ELEVATED = "#222640"
    BG_INPUT = "#12131c"

    # Accent Colors
    ACCENT_CYAN = "#00d4ff"
    ACCENT_PURPLE = "#8b5cf6"
    ACCENT_BLUE = "#3b82f6"
    ACCENT_GREEN = "#10b981"
    ACCENT_ORANGE = "#f59e0b"
    ACCENT_RED = "#ef4444"
    ACCENT_PINK = "#ec4899"

    # Text Colors
    TEXT_PRIMARY = "#f0f2f5"
    TEXT_SECONDARY = "#8892a8"
    TEXT_MUTED = "#555d74"
    TEXT_ACCENT = "#00d4ff"

    # Border
    BORDER_SUBTLE = "#1e2235"
    BORDER_HOVER = "#2d3352"
    BORDER_ACTIVE = "#00d4ff"

    # Theme Compatibility Aliases
    BASE = "#0f1117"             # BG_DARKER
    MANTLE = "#0a0b10"           # BG_DARKEST
    SURFACE0 = "#1a1d2e"         # BG_CARD
    SURFACE1 = "#1f2337"         # BG_CARD_HOVER
    SURFACE2 = "#222640"         # BG_ELEVATED
    TEXT = "#f0f2f5"             # TEXT_PRIMARY
    SUBTEXT0 = "#8892a8"         # TEXT_SECONDARY
    OVERLAY0 = "#555d74"         # TEXT_MUTED
    BLUE = "#3b82f6"             # ACCENT_BLUE
    SAPPHIRE = "#2563eb"         # Darker blue
    TEAL = "#00d4ff"             # ACCENT_CYAN
    SKY = "#38bdf8"              # Sky blue
    GREEN = "#10b981"            # ACCENT_GREEN
    RED = "#ef4444"              # ACCENT_RED
    LAVENDER = "#8b5cf6"         # ACCENT_PURPLE
    PEACH = "#f59e0b"            # ACCENT_ORANGE
    YELLOW = "#eab308"
    CRUST = "#08090d"
    SIDEBAR_BG = "#0d0f18"

    # Gradients (CSS-style for stylesheets)
    GRADIENT_PRIMARY = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #00d4ff,stop:1 #8b5cf6)"
    GRADIENT_CARD = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1a1d2e,stop:1 #151721)"
    GRADIENT_INTERVIEW = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #3b82f6,stop:1 #8b5cf6)"
    GRADIENT_SUPPORT = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #10b981,stop:1 #00d4ff)"
    GRADIENT_ANALYTICS = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #f59e0b,stop:1 #ef4444)"
    GRADIENT_PROFILE = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ec4899,stop:1 #8b5cf6)"

    # Typography
    FONT_FAMILY = "'Segoe UI', 'Inter', 'Roboto', sans-serif"
    FONT_MONO = "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace"
    FONT_SIZE_XS = 11
    FONT_SIZE_SM = 12
    FONT_SIZE_MD = 14
    FONT_SIZE_LG = 16
    FONT_SIZE_XL = 20
    FONT_SIZE_XXL = 28
    FONT_SIZE_HERO = 36

    # Spacing
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 24
    SPACING_XXL = 32

    # Border Radius
    RADIUS_SM = 6
    RADIUS_MD = 10
    RADIUS_LG = 14
    RADIUS_XL = 20
    RADIUS_FULL = 999

    # Shadows (for drop-shadow effects)
    SHADOW_SM = "0 2px 8px rgba(0,0,0,0.3)"
    SHADOW_MD = "0 4px 16px rgba(0,0,0,0.4)"
    SHADOW_LG = "0 8px 32px rgba(0,0,0,0.5)"
    SHADOW_GLOW_CYAN = "0 0 20px rgba(0,212,255,0.15)"
    SHADOW_GLOW_PURPLE = "0 0 20px rgba(139,92,246,0.15)"

    # Sidebar
    SIDEBAR_WIDTH = 260
    SIDEBAR_COLLAPSED_WIDTH = 72
    SIDEBAR_BG = "#0d0e15"

    # TopBar
    TOPBAR_HEIGHT = 60

    @classmethod
    def global_stylesheet(cls):
        """Returns the master QSS stylesheet for the entire application."""
        return f"""
            * {{
                font-family: {cls.FONT_FAMILY};
                color: {cls.TEXT_PRIMARY};
            }}
            QMainWindow, QWidget {{
                background-color: {cls.BG_DARKER};
            }}
            QScrollBar:vertical {{
                background: {cls.BG_DARKEST};
                width: 8px;
                border-radius: 4px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {cls.BG_ELEVATED};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {cls.TEXT_MUTED};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                background: {cls.BG_DARKEST};
                height: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: {cls.BG_ELEVATED};
                border-radius: 4px;
                min-width: 30px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {cls.TEXT_MUTED};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0;
            }}
            QToolTip {{
                background-color: {cls.BG_CARD};
                color: {cls.TEXT_PRIMARY};
                border: 1px solid {cls.BORDER_SUBTLE};
                border-radius: {cls.RADIUS_SM}px;
                padding: 6px 10px;
                font-size: {cls.FONT_SIZE_SM}px;
            }}
            QLineEdit {{
                background-color: {cls.BG_INPUT};
                border: 1px solid {cls.BORDER_SUBTLE};
                border-radius: {cls.RADIUS_MD}px;
                padding: 10px 14px;
                color: {cls.TEXT_PRIMARY};
                font-size: {cls.FONT_SIZE_MD}px;
                selection-background-color: {cls.ACCENT_CYAN};
            }}
            QLineEdit:focus {{
                border-color: {cls.ACCENT_CYAN};
            }}
            QComboBox {{
                background-color: {cls.BG_INPUT};
                border: 1px solid {cls.BORDER_SUBTLE};
                border-radius: {cls.RADIUS_MD}px;
                padding: 8px 12px;
                color: {cls.TEXT_PRIMARY};
                font-size: {cls.FONT_SIZE_MD}px;
            }}
            QComboBox:hover {{
                border-color: {cls.BORDER_HOVER};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {cls.BG_CARD};
                border: 1px solid {cls.BORDER_SUBTLE};
                border-radius: {cls.RADIUS_SM}px;
                color: {cls.TEXT_PRIMARY};
                selection-background-color: {cls.BG_ELEVATED};
            }}
        """
