# ============================================================
#  CONTEXT MANAGER — Window & Environmental Intelligence
#  Detects active desktop application, window title, media
#  playback state, and supported document/zoomable contexts.
# ============================================================

from typing import Dict, Any


class ContextManager:
    """Detects active desktop application, window title, and user focus state."""

    MEDIA_KEYWORDS = [
        'spotify', 'music', 'groove', 'tidal', 'deezer', 'vlc',
        'media player', 'movies & tv', 'video', 'mpv', 'youtube',
        'soundcloud', 'apple music', 'amazon music'
    ]

    ZOOMABLE_KEYWORDS = [
        # VS Code / Code editors
        'visual studio code', 'code', 'vscode', 'pycharm', 'sublime', 'intellij', 'neovim',
        # PowerPoint / Presentations
        'powerpoint', 'pptx', '.ppt', 'slides', 'keynote', 'presentation',
        # Browsers
        'chrome', 'firefox', 'edge', 'opera', 'brave', 'browser', 'arc', 'vivaldi',
        # PDF Viewers
        'acrobat', 'reader', 'pdf', 'foxit', 'sumatrapdf',
        # Image Viewers
        'photos', 'image', 'photo', 'viewer', 'paint', 'irfanview', 'gimp', 'photoshop'
    ]

    @staticmethod
    def get_active_window_title() -> str:
        """Returns the lowercased title of the currently focused foreground window."""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active and active.title:
                return active.title.strip().lower()
        except Exception:
            pass

        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return win32gui.GetWindowText(hwnd).strip().lower()
        except Exception:
            pass

        return ""

    @staticmethod
    def is_media_active() -> bool:
        """Checks if a media player or media playback tab is currently active."""
        title = ContextManager.get_active_window_title()
        if not title:
            return False
        return any(kw in title for kw in ContextManager.MEDIA_KEYWORDS)

    @staticmethod
    def is_zoomable_app() -> bool:
        """Checks if the foreground app is a supported zoomable document (VS Code, PowerPoint, Browser, PDF, Image)."""
        title = ContextManager.get_active_window_title()
        if not title:
            return False
        return any(kw in title for kw in ContextManager.ZOOMABLE_KEYWORDS)

    @staticmethod
    def detect_context() -> str:
        """Categorizes foreground application into structured context categories."""
        title = ContextManager.get_active_window_title()
        if not title:
            return 'default'

        # Media takes priority if media app is focused
        if any(kw in title for kw in ['spotify', 'music', 'groove', 'tidal', 'deezer']):
            return 'spotify'
        if any(kw in title for kw in ['vlc', 'media player', 'movies & tv', 'video', 'mpv']):
            return 'vlc'
        if any(kw in title for kw in ['powerpoint', 'pptx', '.ppt', 'slides', 'keynote', 'presentation']):
            return 'powerpoint'
        if any(kw in title for kw in ['code', 'visual studio', 'vscode', 'pycharm', 'sublime', 'intellij', 'neovim']):
            return 'code_editor'
        if any(kw in title for kw in ['chrome', 'firefox', 'edge', 'opera', 'brave', 'browser', 'arc']):
            return 'browser'
        if any(kw in title for kw in ['acrobat', 'reader', 'pdf', 'foxit', 'sumatrapdf']):
            return 'pdf_viewer'
        if any(kw in title for kw in ['photos', 'image', 'photo', 'viewer', 'paint', 'irfanview']):
            return 'image_viewer'
        if any(kw in title for kw in ['explorer', 'files', 'folder', 'this pc', 'finder']):
            return 'file_explorer'
        if any(kw in title for kw in ['notepad', 'word', '.docx', '.txt', 'writer', 'docs']):
            return 'text_editor'

        if any(kw in title for kw in ContextManager.MEDIA_KEYWORDS):
            return 'media'

        return 'default'

    @staticmethod
    def get_current_context() -> Dict[str, Any]:
        """Returns structured context payload for AI reasoning and gesture dispatching."""
        title = ContextManager.get_active_window_title()
        detected = ContextManager.detect_context()
        return {
            "active_window_title": title,
            "detected_app": detected,
            "is_media": ContextManager.is_media_active(),
            "is_zoomable": ContextManager.is_zoomable_app()
        }
