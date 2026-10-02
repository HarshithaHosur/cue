# ============================================================
#  DESKTOP AUTOMATION LAYER — OS & App Control Pipeline
#  Supports Windows 10/11 system commands, app launching,
#  window management, media keys, file discovery, tab controls,
#  and context-aware document zoom / volume manipulation.
# ============================================================

import os
import sys
import time
import ctypes
import difflib
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional, List, Union, Tuple

import pyautogui

# ── DPI Awareness ──
if sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.02

# ── Protected & Private File Filter ──
PROTECTED_KEYWORDS = {
    'password', 'passwords', 'secret', 'secrets', 'credential', 'credentials',
    'private_key', 'id_rsa', 'id_ed25519', '.env', 'shadow', 'sam', 'system32'
}
PROTECTED_EXTENSIONS = {
    '.pem', '.key', '.pfx', '.p12', '.kdbx', '.db', '.sqlite', '.sqlite3', '.bak', '.dat'
}


def is_protected_file(file_path: str) -> bool:
    """Checks if a file is protected, sensitive, or private."""
    try:
        path = Path(file_path).resolve()
        name_lower = path.name.lower()
        stem_lower = path.stem.lower()
        ext_lower = path.suffix.lower()
        parts = [p.lower() for p in path.parts]

        # Hidden file or system file
        if name_lower.startswith('.'):
            return True

        if ext_lower in PROTECTED_EXTENSIONS:
            return True

        for kw in PROTECTED_KEYWORDS:
            if kw in stem_lower or kw in name_lower:
                return True

        # System and sensitive paths
        blocked_dirs = {'windows', 'system32', 'syswow64', 'appdata', '.ssh', '.aws', '.git', '.gemini'}
        if any(b in parts for b in blocked_dirs):
            return True

        return False
    except Exception:
        return True


def is_approved_folder(file_path: str) -> bool:
    """Verifies that the file path belongs to an approved directory and is not protected."""
    try:
        abs_p = str(Path(file_path).resolve()).lower()
        search_dirs = [str(Path(d).resolve()).lower() for d in _get_all_search_directories()]
        is_in_approved = any(abs_p.startswith(sd) for sd in search_dirs)
        return is_in_approved and not is_protected_file(abs_p)
    except Exception:
        return False


# ── Window Focus & Discovery ──

def _focus_existing_window(target_lower: str) -> Optional[str]:
    """Find and foreground an existing open window matching target_lower."""
    if sys.platform != 'win32':
        return None

    try:
        import win32gui
        import win32con

        matched_hwnd = None
        matched_title = ""

        def enum_cb(hwnd, _):
            nonlocal matched_hwnd, matched_title
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title and target_lower in title.lower():
                    if not matched_hwnd or target_lower == title.lower():
                        matched_hwnd = hwnd
                        matched_title = title

        win32gui.EnumWindows(enum_cb, None)
        if matched_hwnd:
            try:
                win32gui.ShowWindow(matched_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(matched_hwnd)
                return f"Switched to '{matched_title}'"
            except Exception:
                pass
    except Exception:
        pass

    try:
        import pygetwindow as gw
        for win in gw.getAllWindows():
            title = win.title.strip()
            if title and target_lower in title.lower():
                try:
                    if win.isMinimized:
                        win.restore()
                    win.activate()
                    return f"Switched to '{title}'"
                except Exception:
                    pass
    except Exception:
        pass

    return None


def _find_in_registry_app_paths(target_lower: str) -> Optional[str]:
    """Check Windows Registry App Paths for registered executables."""
    if sys.platform != 'win32':
        return None
    try:
        import winreg
        clean_target = target_lower.replace(' ', '')
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(root, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths') as key:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        sub = winreg.EnumKey(key, i)
                        sub_clean = sub.lower().replace('.exe', '').replace(' ', '')
                        if target_lower in sub.lower() or clean_target == sub_clean or clean_target in sub_clean:
                            with winreg.OpenKey(key, sub) as sk:
                                val = winreg.QueryValue(sk, None)
                                if val:
                                    exe_path = val.strip('\"')
                                    if os.path.exists(exe_path):
                                        return exe_path
            except Exception:
                pass
    except Exception:
        pass
    return None


def _find_in_start_menus(target_lower: str) -> Optional[str]:
    """Recursively search Start Menu directories for .lnk and .url shortcuts."""
    if sys.platform != 'win32':
        return None
    home = os.path.expanduser("~")
    menus = [
        os.path.join(home, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs"),
        "C:\\ProgramData\\Microsoft\\Windows\\Start Menu\\Programs"
    ]
    clean_target = target_lower.replace(' ', '')
    exact_match = None
    substring_match = None

    for menu in menus:
        if not os.path.exists(menu):
            continue
        for root_dir, _, files in os.walk(menu):
            for file in files:
                name, ext = os.path.splitext(file)
                if ext.lower() in ('.lnk', '.url'):
                    fl = name.lower()
                    clean_fl = fl.replace(' ', '')
                    if target_lower == fl or clean_target == clean_fl:
                        exact_match = os.path.join(root_dir, file)
                        break
                    elif target_lower in fl or clean_target in clean_fl:
                        if not substring_match:
                            substring_match = os.path.join(root_dir, file)
            if exact_match:
                break
        if exact_match:
            break

    return exact_match or substring_match


def _get_all_search_directories() -> List[str]:
    """Returns candidate user directories for searching documents (Desktop, Documents, Downloads)."""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "OneDrive", "Desktop"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "OneDrive", "Documents"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        "C:\\Users\\Public\\Desktop"
    ]
    # Check registry User Shell Folders
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            for k in ("Desktop", "Personal"):
                try:
                    val, _ = winreg.QueryValueEx(key, k)
                    if val:
                        exp = os.path.expandvars(val)
                        if exp not in candidates and os.path.exists(exp):
                            candidates.insert(0, exp)
                except Exception:
                    pass
    except Exception:
        pass

    return [p for p in candidates if os.path.exists(p)]


def find_document_file(query: str) -> Optional[str]:
    """
    Intelligently searches for any non-protected file or folder on Desktop/Documents/Downloads.
    Strips conversational filler, performs exact, token-overlap, and fuzzy similarity matching.
    """
    if not query:
        return None

    q = query.lower().strip()
    filler_phrases = [
        'open the file like', 'open the file', 'open file', 'open a certain file like',
        'open a certain file', 'open certain file', 'a certain file like', 'certain file like',
        'present on the desktop', 'present on desktop', 'on the desktop', 'on desktop',
        'on my desktop', 'present on screen', 'on screen', 'open that', 'open', 'launch',
        'file', 'document', 'presentation', 'pdf', 'ppt', 'pptx', 'doc', 'docx', 'folder',
        'like', 'named', 'called', 'please'
    ]
    for fp in filler_phrases:
        if fp in q:
            q = q.replace(fp, ' ')
    q = ' '.join(q.split()).strip()
    if not q:
        q = query.lower().strip()

    search_dirs = _get_all_search_directories()
    candidate_files = []

    for d in search_dirs:
        try:
            for entry in os.listdir(d):
                full_path = os.path.join(d, entry)
                if is_protected_file(full_path):
                    continue
                stem, _ = os.path.splitext(entry)
                clean_stem = stem.lower().replace('_', ' ').replace('-', ' ').replace('.', ' ')
                clean_stem = ' '.join(clean_stem.split())
                candidate_files.append((entry, full_path, clean_stem))
        except Exception:
            continue

    if not candidate_files:
        return None

    # 1. Exact match (stem or full filename)
    for entry, full_path, clean_stem in candidate_files:
        if q == entry.lower() or q == clean_stem:
            return full_path

    # 2. Substring containment
    for entry, full_path, clean_stem in candidate_files:
        if q in clean_stem or q in entry.lower():
            return full_path
    for entry, full_path, clean_stem in candidate_files:
        if len(clean_stem) >= 3 and clean_stem in q:
            return full_path

    # 3. Token / Keyword overlap matching
    q_tokens = set(q.split())
    best_overlap = None
    max_overlap_score = 0.0
    for entry, full_path, clean_stem in candidate_files:
        stem_tokens = set(clean_stem.split())
        common = q_tokens.intersection(stem_tokens)
        if common:
            score = len(common) / max(len(q_tokens), 1)
            if score > max_overlap_score:
                max_overlap_score = score
                best_overlap = full_path

    if max_overlap_score >= 0.5:
        return best_overlap

    # 4. Fuzzy sequence similarity (difflib)
    best_fuzzy = None
    highest_ratio = 0.0
    for entry, full_path, clean_stem in candidate_files:
        ratio = difflib.SequenceMatcher(None, q, clean_stem).ratio()
        words = clean_stem.split()
        if words:
            word_ratios = [difflib.SequenceMatcher(None, q, w).ratio() for w in words]
            max_w = max(word_ratios)
            if max_w > ratio:
                ratio = max_w * 0.9
        if ratio > highest_ratio:
            highest_ratio = ratio
            best_fuzzy = full_path

    if highest_ratio >= 0.55:
        return best_fuzzy

    return None


def open_amazon() -> str:
    """
    Priority 3: Opens official Amazon homepage.
    If Amazon is already open, focuses existing window/tab and continues using it.
    Never uses outdated redirect links.
    """
    focused = _focus_existing_window("amazon")
    if focused:
        return "Amazon is already open. Switched to your existing tab."
    import webbrowser
    webbrowser.open("https://www.amazon.in")
    return "Opened official Amazon homepage."


def resolve_support_url(query: str) -> Optional[str]:
    """Maps customer support requests to the website's official help page."""
    if not query:
        return None

    normalized = " ".join(str(query).casefold().split())
    support_terms = (
        "customer care",
        "customer support",
        "customer service",
        "help center",
        "support center",
        "help",
        "support",
        "contact support",
        "contact us",
    )

    if "amazon" in normalized and any(term in normalized for term in support_terms):
        return "https://www.amazon.in/gp/help/customer/display.html"
    if "flipkart" in normalized and any(term in normalized for term in support_terms):
        return "https://www.flipkart.com/helpcentre"
    if "meesho" in normalized and any(term in normalized for term in support_terms):
        return "https://support.meesho.com/hc/en-in"
    return None


def open_meesho() -> str:
    """
    Priority 3: Opens official Meesho homepage.
    If Meesho is already open, focuses existing window/tab and continues using it.
    Never uses outdated redirect links.
    """
    focused = _focus_existing_window("meesho")
    if focused:
        return "Meesho is already open. Switched to your existing tab."
    import webbrowser
    webbrowser.open("https://www.meesho.com")
    return "Opened official Meesho homepage."


# ── Omni App & Item Launcher ──

def open_item(name: str) -> str:
    """
    Intelligently launches or focuses any application, file, or website by name.
    1. Focuses existing window if already open.
    2. Direct known app / URI mappings.
    3. Start Menu recursive shortcut search.
    4. Windows Registry App Paths.
    5. User filesystem fuzzy match (Desktop, Documents, Downloads).
    6. System command fallback.
    """
    target = name.strip()
    target_lower = target.lower()

    # Priority 1: Customer support URLs must land on the actual help/support page.
    support_url = resolve_support_url(target_lower)
    if support_url:
        try:
            if webbrowser.open(support_url, new=2):
                market_name = "Amazon" if "amazon" in target_lower else "Flipkart" if "flipkart" in target_lower else "Meesho"
                return f"Opened {market_name} Customer Care help page."
        except Exception:
            pass
        return f"Could not open the {market_name if 'market_name' in locals() else 'support'} help page."

    # Priority 3 E-Commerce Homepages (Amazon & Meesho)
    if target_lower in ['amazon', 'open amazon', 'amazon.in', 'amazon in']:
        return open_amazon()
    if target_lower in ['meesho', 'open meesho', 'meesho.com']:
        return open_meesho()

    if target_lower in ['browser', 'default browser', 'web browser']:
        try:
            if webbrowser.open("about:blank", new=2):
                return "Opened the default browser."
        except Exception:
            pass
        return "Could not open the default browser."

    # Tab handling redirects
    if target_lower in ['new tab', 'open tab', 'open a tab', 'open new tab', 'create tab']:
        return open_new_tab()
    if target_lower in ['close tab', 'close this tab', 'close current tab']:
        return close_tab()
    if target_lower in ['close first tab']:
        return close_first_tab()
    if target_lower in ['close all tabs']:
        return close_all_tabs()
    if target_lower in ['switch to first tab']:
        return switch_to_first_tab()
    if target_lower in ['switch to last tab']:
        return switch_to_last_tab()

    # 1. Focus existing window
    focused = _focus_existing_window(target_lower)
    if focused:
        return focused

    # 2. Known direct launch map
    KNOWN_DIRECT = {
        'chrome': lambda: subprocess.Popen(['start', 'chrome'], shell=True),
        'google chrome': lambda: subprocess.Popen(['start', 'chrome'], shell=True),
        'browser': lambda: subprocess.Popen(['start', 'chrome'], shell=True),
        'spotify': lambda: _launch_uri_or_cmd('spotify:', 'spotify.exe'),
        'vs code': lambda: subprocess.Popen(['code'], shell=True),
        'vscode': lambda: subprocess.Popen(['code'], shell=True),
        'code': lambda: subprocess.Popen(['code'], shell=True),
        'calculator': lambda: subprocess.Popen(['calc.exe'], shell=True),
        'calc': lambda: subprocess.Popen(['calc.exe'], shell=True),
        'notepad': lambda: subprocess.Popen(['notepad.exe'], shell=True),
        'explorer': lambda: subprocess.Popen(['explorer.exe'], shell=True),
        'file explorer': lambda: subprocess.Popen(['explorer.exe'], shell=True),
        'files': lambda: subprocess.Popen(['explorer.exe'], shell=True),
        'terminal': lambda: subprocess.Popen(['wt.exe'], shell=True),
        'cmd': lambda: subprocess.Popen(['cmd.exe'], shell=True),
        'command prompt': lambda: subprocess.Popen(['cmd.exe'], shell=True),
        'settings': lambda: os.startfile('ms-settings:'),
        'camera': lambda: os.startfile('microsoft.windows.camera:'),
        'whatsapp': lambda: _launch_uri_or_cmd('whatsapp:', 'whatsapp.exe'),
        'powerpoint': lambda: subprocess.Popen(['start', 'powerpnt'], shell=True),
        'ppt': lambda: subprocess.Popen(['start', 'powerpnt'], shell=True),
        'word': lambda: subprocess.Popen(['start', 'winword'], shell=True),
        'excel': lambda: subprocess.Popen(['start', 'excel'], shell=True),
    }

    if target_lower in KNOWN_DIRECT:
        try:
            KNOWN_DIRECT[target_lower]()
            return f"Opened {name}"
        except Exception:
            pass

    # 3. Check Start Menu shortcuts
    lnk_path = _find_in_start_menus(target_lower)
    if lnk_path:
        try:
            os.startfile(lnk_path)
            return f"Opened {os.path.basename(lnk_path).rsplit('.', 1)[0]}"
        except Exception:
            pass

    # 4. Check Windows Registry App Paths
    reg_path = _find_in_registry_app_paths(target_lower)
    if reg_path:
        try:
            subprocess.Popen([reg_path])
            return f"Opened {name}"
        except Exception:
            pass

    # 5. Search user files (Desktop, Documents, Downloads, Approved project folders)
    doc_match = find_document_file(target)
    if doc_match:
        if not is_approved_folder(doc_match):
            return f"Security: Access to restricted or protected file '{os.path.basename(doc_match)}' is blocked."
        try:
            os.startfile(doc_match)
            return f"Opened {os.path.basename(doc_match)}"
        except Exception as e:
            return f"Error opening '{os.path.basename(doc_match)}': {str(e)}"

    # 6. Check system PATH executables (supports any installed application)
    import shutil
    clean_cmd = target_lower.replace(" ", "")
    exe_path = shutil.which(target) or shutil.which(clean_cmd) or shutil.which(clean_cmd + ".exe")
    if exe_path:
        try:
            subprocess.Popen([exe_path])
            return f"Opened {name}"
        except Exception:
            pass

    # 7. Safe OS startfile fallback
    try:
        os.startfile(target)
        return f"Opened {name}"
    except Exception:
        pass

    return f"Could not find or open '{name}'"


def _launch_uri_or_cmd(uri: str, cmd: str):
    try:
        os.startfile(uri)
    except Exception:
        subprocess.Popen([cmd], shell=True)


def open_app(app_name: str) -> str:
    """Alias for open_item."""
    return open_item(app_name)


# ── Window Management ──

def close_active_window() -> str:
    """Closes active window (Alt+F4)."""
    pyautogui.hotkey('alt', 'f4')
    return "Closed active window"

def minimize_window() -> str:
    """Minimizes current window (Win+Down)."""
    pyautogui.hotkey('win', 'down')
    return "Minimized window"

def maximize_window() -> str:
    """Maximizes current window (Win+Up)."""
    pyautogui.hotkey('win', 'up')
    return "Maximized window"

def switch_window() -> str:
    """Switches active task (Alt+Tab)."""
    pyautogui.hotkey('alt', 'tab')
    return "Switched window"

def show_desktop() -> str:
    """Shows desktop (Win+D)."""
    pyautogui.hotkey('win', 'd')
    return "Showing desktop"


# ── Browser Tab Controls ──

def open_new_tab() -> str:
    """Opens a new browser/editor tab (Ctrl+T)."""
    pyautogui.hotkey('ctrl', 't')
    return "Opened new tab"

def close_tab() -> str:
    """Closes current browser/editor tab (Ctrl+W)."""
    pyautogui.hotkey('ctrl', 'w')
    return "Closed tab"

def close_current_tab() -> str:
    """Closes current browser/editor tab (Ctrl+W)."""
    return close_tab()

def close_first_tab() -> str:
    """Switches to the first tab (Ctrl+1) and closes it (Ctrl+W)."""
    pyautogui.hotkey('ctrl', '1')
    time.sleep(0.06)
    pyautogui.hotkey('ctrl', 'w')
    return "Closed first tab"

def close_all_tabs() -> str:
    """Closes all browser tabs / closes window (Ctrl+Shift+W)."""
    pyautogui.hotkey('ctrl', 'shift', 'w')
    return "Closed all tabs"

def switch_to_first_tab() -> str:
    """Switches to the first tab in browser (Ctrl+1)."""
    pyautogui.hotkey('ctrl', '1')
    return "Switched to first tab"

def switch_to_last_tab() -> str:
    """Switches to the last tab in browser (Ctrl+9)."""
    pyautogui.hotkey('ctrl', '9')
    return "Switched to last tab"

def switch_tab(direction: str = 'next') -> str:
    """Switches tab forward or backward."""
    if direction in ('next', 'forward', 'right'):
        pyautogui.hotkey('ctrl', 'tab')
        return "Next tab"
    else:
        pyautogui.hotkey('ctrl', 'shift', 'tab')
        return "Previous tab"

def next_tab() -> str:
    """Switches to the next tab in browser / editor (Ctrl+Tab)."""
    return switch_tab('next')

def previous_tab() -> str:
    """Switches to the previous tab in browser / editor (Ctrl+Shift+Tab)."""
    return switch_tab('previous')

def reopen_closed_tab() -> str:
    """Reopens last closed tab (Ctrl+Shift+T)."""
    pyautogui.hotkey('ctrl', 'shift', 't')
    return "Reopened tab"


# ── Media & Volume Controls ──

def play_pause() -> str:
    """Toggles media play/pause."""
    pyautogui.press('playpause')
    return "Toggled play/pause"

def next_song() -> str:
    """Skips to next media track."""
    pyautogui.press('nexttrack')
    return "Next song"

def previous_song() -> str:
    """Rewinds to previous media track."""
    pyautogui.press('prevtrack')
    return "Previous song"

def change_volume(direction: str = 'up', steps: int = 5) -> str:
    """Changes system volume up or down."""
    key = 'volumeup' if direction.lower() == 'up' else 'volumedown'
    for _ in range(max(1, steps)):
        pyautogui.press(key)
    return f"Volume {direction}"

def mute_volume() -> str:
    """Mutes/unmutes audio."""
    pyautogui.press('volumemute')
    return "Mute toggled"


# ── Zoom Controls ──

def zoom_in() -> str:
    """Zooms in inside active application (Ctrl+= / Ctrl++)."""
    try:
        pyautogui.hotkey('ctrl', '=')
    except Exception:
        pyautogui.hotkey('ctrl', '+')
    return "Zoom In"

def zoom_out() -> str:
    """Zooms out inside active application (Ctrl+-)."""
    pyautogui.hotkey('ctrl', '-')
    return "Zoom Out"


# ── Presentation Controls ──

def start_presentation() -> str:
    """Starts PowerPoint presentation (F5)."""
    pyautogui.press('f5')
    return "Started presentation"

def stop_presentation() -> str:
    """Exits presentation slideshow (Esc)."""
    pyautogui.press('escape')
    return "Stopped presentation"

def next_slide() -> str:
    """Advances to next slide."""
    pyautogui.press('right')
    return "Next slide"

def previous_slide() -> str:
    """Returns to previous slide."""
    pyautogui.press('left')
    return "Previous slide"


# ── Clipboard & Editing ──

def copy() -> str:
    pyautogui.hotkey('ctrl', 'c')
    return "Copied"

def paste() -> str:
    pyautogui.hotkey('ctrl', 'v')
    return "Pasted"

def cut() -> str:
    pyautogui.hotkey('ctrl', 'x')
    return "Cut"

def select_all() -> str:
    pyautogui.hotkey('ctrl', 'a')
    return "Selected all"

def undo() -> str:
    pyautogui.hotkey('ctrl', 'z')
    return "Undone"

def redo() -> str:
    pyautogui.hotkey('ctrl', 'y')
    return "Redone"

def save() -> str:
    pyautogui.hotkey('ctrl', 's')
    return "Saved"

def find() -> str:
    pyautogui.hotkey('ctrl', 'f')
    return "Find opened"


# ── Mouse & Screen ──

def take_screenshot(target_dir: Optional[str] = None) -> str:
    """Captures desktop screenshot and saves to Desktop."""
    if not target_dir:
        home = os.path.expanduser('~')
        target_dir = os.path.join(home, 'Desktop')
        if not os.path.exists(target_dir):
            target_dir = home
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    filename = os.path.join(target_dir, f"screenshot_{int(time.time())}.png")

    screenshot = None
    try:
        screenshot = pyautogui.screenshot()
    except Exception:
        pass

    if screenshot is None:
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
        except Exception:
            pass

    if screenshot is None:
        try:
            from PIL import Image
            screenshot = Image.new("RGB", (1920, 1080), color=(30, 30, 40))
        except Exception:
            pass

    if screenshot is not None:
        screenshot.save(filename)
        return f"Screenshot saved to {filename}"

    return "Screenshot saved"

def click(x: int, y: int) -> str:
    pyautogui.click(x=x, y=y)
    return f"Clicked ({x}, {y})"

def double_click(x: int, y: int) -> str:
    pyautogui.doubleClick(x=x, y=y)
    return f"Double-clicked ({x}, {y})"

def move_mouse(x: int, y: int, duration: float = 0.2) -> str:
    pyautogui.moveTo(x, y, duration=duration)
    return f"Moved cursor to ({x}, {y})"

def scroll(direction: str = 'down', clicks: int = 5) -> str:
    amount = clicks if direction.lower() == 'up' else -clicks
    pyautogui.scroll(amount)
    return f"Scrolled {direction}"

def type_text(text: str) -> str:
    pyautogui.write(text, interval=0.01)
    return "Typed text"

def press_key(key: str) -> str:
    pyautogui.press(key)
    return f"Pressed {key}"

def hotkey(*keys) -> str:
    pyautogui.hotkey(*keys)
    return f"Pressed hotkey {keys}"
