# ============================================================
#  STRUCTURED SCREEN CONTEXT — Multimodal Scene Intelligence
#  Combines window metadata, OCR element geometry, website
#  classification, page type identification, and UI interaction targets.
# ============================================================

import re
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class ScreenElement:
    """Represents a visible, interactive element on screen with spatial coordinates."""
    label: str
    element_type: str  # 'button', 'input', 'menu', 'tab', 'card', 'text', 'error'
    bbox: List[int]    # [x1, y1, x2, y2]
    center_x: int
    center_y: int
    width: int
    height: int
    confidence: float = 1.0


@dataclass
class ScreenContext:
    """
    Structured representation of the user's visible desktop/application state.
    Used as the single source of truth for all assistant reasoning.
    """
    timestamp: float
    active_application: str
    active_window_title: str
    is_browser: bool
    browser_name: Optional[str]
    website: str                 # "Amazon", "Meesho", "Flipkart", "GitHub", "Zomato", etc.
    current_page: str            # "Home", "Orders", "Cart", "Returns", "Help", "Customer Support", "Product Page", "Checkout", "Terminal", "Code", etc.
    is_support_page: bool
    width: int
    height: int
    current_cursor_position: List[int] = field(default_factory=list)
    current_user_goal: str = ""
    selected_item: str = ""
    automation_confidence: float = 0.0

    # Extracted UI elements
    visible_buttons: List[Dict[str, Any]] = field(default_factory=list)
    visible_forms: List[Dict[str, Any]] = field(default_factory=list)
    visible_menus: List[Dict[str, Any]] = field(default_factory=list)
    visible_tabs: List[Dict[str, Any]] = field(default_factory=list)
    dialogs: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    highlighted_elements: List[Dict[str, Any]] = field(default_factory=list)

    # Text & errors
    ocr_lines: List[str] = field(default_factory=list)
    ocr_blocks: List[Dict[str, Any]] = field(default_factory=list)
    detected_errors: List[Dict[str, Any]] = field(default_factory=list)

    # Terminal state
    is_terminal: bool = False
    terminal_type: str = "none"  # "git", "python", "node", "java", "powershell", "cmd", "vscode"

    # Full text representation
    full_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def find_button(self, name_or_keyword: str) -> Optional[Dict[str, Any]]:
        """Finds the most relevant button matching the target query."""
        q = name_or_keyword.lower().strip()
        # 1. Exact match on visible_buttons
        for btn in self.visible_buttons:
            lbl = btn.get("label", "").lower().strip()
            if q == lbl or q in lbl or lbl in q:
                return btn

        # 2. Check all OCR blocks for matching text
        for blk in self.ocr_blocks:
            txt = blk.get("text", "").lower().strip()
            if q in txt or txt in q:
                bbox = blk.get("bbox", [0, 0, 0, 0])
                cx = (bbox[0] + bbox[2]) // 2
                cy = (bbox[1] + bbox[3]) // 2
                return {
                    "label": blk.get("text", ""),
                    "type": "button",
                    "bbox": bbox,
                    "x": cx,
                    "y": cy,
                    "w": bbox[2] - bbox[0],
                    "h": bbox[3] - bbox[1],
                    "confidence": blk.get("confidence", 0.9)
                }
        return None

    def find_text_snippet(self, keyword: str) -> Optional[str]:
        q = keyword.lower()
        for line in self.ocr_lines:
            if q in line.lower():
                return line
        return None


# ────────────────────────────────────────────────────────────
#  SCREEN CONTEXT BUILDER (Rule Engine + OCR Geometry)
# ────────────────────────────────────────────────────────────

KNOWN_BUTTON_PATTERNS = [
    # E-Commerce & Retail
    re.compile(r'\b(cart|shopping bag|bag|shopping cart|view cart)\b', re.IGNORECASE),
    re.compile(r'\b(returns\s*&\s*orders|your orders|my orders|returns|order details)\b', re.IGNORECASE),
    re.compile(r'\b(return or replace items?|replace items?|return items?|request return)\b', re.IGNORECASE),
    re.compile(r'\b(buy now|add to cart|proceed to checkout|place your order|checkout)\b', re.IGNORECASE),
    re.compile(r'\b(customer (?:service|support)|help centre?|contact us|need help\??)\b', re.IGNORECASE),
    re.compile(r'\b(track package|order status|track order)\b', re.IGNORECASE),
    re.compile(r'\b(apply promo|apply coupon|redeem)\b', re.IGNORECASE),
    re.compile(r'\b(sign in|sign out|login|log out|account & lists)\b', re.IGNORECASE),
    re.compile(r'\b(download statement|view statement|download invoice)\b', re.IGNORECASE),
    re.compile(r'\b(continue|submit|confirm|cancel|back|done|save|apply|next|search)\b', re.IGNORECASE)
]

KNOWN_PAGE_MARKERS = {
    "order_details": ["order details", "order summary", "order placed", "order #", "shipment details"],
    "replacement": ["replacement request", "replace this item", "replacement options", "replacement order"],
    "refund": ["refund status", "refund issued", "refund details", "refund to", "refund processed"],
    "search_results": ["results for", "search results", "products matching", "sort by", "filters"],
    "cart": ["cart", "shopping cart", "shopping bag", "subtotal", "proceed to buy", "empty cart"],
    "orders": ["your orders", "returns & orders", "order history", "placed on", "order #", "track package"],
    "returns": ["return or replace", "choose items to return", "return status", "why are you returning", "refund to"],
    "support": ["customer service", "help centre", "customer support", "how can we help", "contact us", "help with this order"],
    "product": ["buy now", "add to cart", "in stock", "m.r.p", "inclusive of all taxes", "free delivery", "product details"],
    "checkout": ["select a payment method", "checkout", "place your order", "shipping address", "delivery address", "order summary"],
    "home": ["welcome", "best sellers", "todays deals", "categories", "trending", "explore", "top offers"]
}


def build_screen_context(
    window_info: Dict[str, Any],
    ocr_result: Dict[str, Any],
    width: int,
    height: int
) -> ScreenContext:
    """
    Constructs a rich, reliable ScreenContext object from raw window metrics and OCR extraction.
    """
    raw_title = window_info.get("title", "")
    title_lower = raw_title.lower()
    app_name = window_info.get("app_name", "Desktop")
    is_browser = window_info.get("is_browser", False)
    browser_name = window_info.get("browser_name")

    lines = ocr_result.get("lines", [])
    blocks = ocr_result.get("blocks", [])
    full_text = ocr_result.get("full_text", "")
    full_text_lower = full_text.lower()
    detected_errors = ocr_result.get("detected_errors", [])

    # 1. Detect Website
    website = "General Application"
    if "amazon" in title_lower or "amazon" in full_text_lower:
        website = "Amazon"
    elif "meesho" in title_lower or "meesho" in full_text_lower:
        website = "Meesho"
    elif "flipkart" in title_lower or "flipkart" in full_text_lower:
        website = "Flipkart"
    elif "myntra" in title_lower or "myntra" in full_text_lower:
        website = "Myntra"
    elif "github" in title_lower or "github" in full_text_lower:
        website = "GitHub"
    elif "zomato" in title_lower or "zomato" in full_text_lower:
        website = "Zomato"
    elif "swiggy" in title_lower or "swiggy" in full_text_lower:
        website = "Swiggy"
    elif is_browser:
        website = "Web Browser"

    # 2. Detect Terminal or IDE
    is_terminal = (
        ocr_result.get("is_terminal_like", False) or
        any(t in title_lower for t in ["powershell", "cmd", "terminal", "bash", "command prompt", "visual studio code", "vs code"])
    )
    terminal_type = "none"
    if is_terminal:
        if "git" in full_text_lower or "fatal:" in full_text_lower or "not a git repository" in full_text_lower:
            terminal_type = "git"
        elif "python" in full_text_lower or "traceback" in full_text_lower or "modulenotfounderror" in full_text_lower:
            terminal_type = "python"
        elif "npm" in full_text_lower or "node" in full_text_lower:
            terminal_type = "node"
        elif "java" in full_text_lower or "nullpointer" in full_text_lower:
            terminal_type = "java"
        elif "powershell" in title_lower or "powershell" in full_text_lower:
            terminal_type = "powershell"
        elif "cmd" in title_lower or "command prompt" in title_lower:
            terminal_type = "cmd"
        elif "visual studio code" in title_lower or "vs code" in title_lower:
            terminal_type = "vscode"

    # 3. Detect Current Page
    current_page = "Standard Window"
    is_support = False

    if is_terminal:
        current_page = "Terminal / Command Prompt"
    elif website in ["Amazon", "Meesho", "Flipkart", "Myntra", "Web Browser"]:
        # Match page markers against title and full screen text
        scores = {p: 0 for p in KNOWN_PAGE_MARKERS}
        for p, keywords in KNOWN_PAGE_MARKERS.items():
            for kw in keywords:
                if kw in title_lower:
                    scores[p] += 3
                if kw in full_text_lower:
                    scores[p] += 1

        best_page = max(scores, key=scores.get)
        if scores[best_page] > 0:
            page_name_map = {
                "order_details": "Order Details",
                "replacement": "Replacement Page",
                "refund": "Refund Page",
                "search_results": "Search Results",
                "cart": "Cart",
                "orders": "Orders",
                "returns": "Returns",
                "support": "Customer Support",
                "product": "Product Page",
                "checkout": "Checkout",
                "home": "Home"
            }
            current_page = page_name_map.get(best_page, "Home")
            if current_page in ["Returns", "Customer Support"]:
                is_support = True
        else:
            current_page = "Home"

    # 4. Extract Visible Buttons & Interactive Elements
    visible_buttons = []
    visible_forms = []
    visible_menus = []
    visible_tabs = []
    dialogs = []
    warnings = []

    try:
        import pyautogui
        cursor = pyautogui.position()
        cursor_position = [int(cursor.x), int(cursor.y)]
    except Exception:
        cursor_position = []

    for blk in blocks:
        txt = blk.get("text", "").strip()
        if not txt or len(txt) > 60:
            continue
        bbox = blk.get("bbox", [0, 0, 0, 0])
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        cx = (bbox[0] + bbox[2]) // 2
        cy = (bbox[1] + bbox[3]) // 2
        conf = blk.get("confidence", 0.9)

        # Check against button patterns
        is_btn = False
        for pat in KNOWN_BUTTON_PATTERNS:
            if pat.search(txt):
                is_btn = True
                break

        if is_btn:
            visible_buttons.append({
                "label": txt,
                "type": "button",
                "bbox": bbox,
                "x": cx,
                "y": cy,
                "w": w,
                "h": h,
                "confidence": conf
            })
        elif any(f_kw in txt.lower() for f_kw in ["search", "enter", "type here", "email", "password"]):
            visible_forms.append({
                "label": txt,
                "type": "input",
                "bbox": bbox,
                "x": cx,
                "y": cy,
                "w": w,
                "h": h
            })
        if any(term in txt.lower() for term in ["warning", "caution", "error", "failed", "permission required"]):
            warnings.append({"text": txt, "bbox": bbox, "confidence": conf})
        if any(term in txt.lower() for term in ["dialog", "are you sure", "confirm", "allow access", "permission"]):
            dialogs.append({"text": txt, "bbox": bbox, "confidence": conf})
        if any(term in txt.lower() for term in ["menu", "more options", "navigation"]):
            visible_menus.append({"label": txt, "bbox": bbox, "x": cx, "y": cy, "confidence": conf})
        elif cy < 120 and w > 40:
            # Top navigation tabs / menus
            visible_tabs.append({
                "label": txt,
                "type": "tab",
                "bbox": bbox,
                "x": cx,
                "y": cy
            })

    return ScreenContext(
        timestamp=time.time(),
        active_application=app_name,
        active_window_title=raw_title,
        is_browser=is_browser,
        browser_name=browser_name,
        website=website,
        current_page=current_page,
        is_support_page=is_support,
        width=width,
        height=height,
        current_cursor_position=cursor_position,
        automation_confidence=0.0,
        visible_buttons=visible_buttons,
        visible_forms=visible_forms,
        visible_menus=visible_menus,
        visible_tabs=visible_tabs,
        dialogs=dialogs,
        warnings=warnings,
        ocr_lines=lines,
        ocr_blocks=blocks,
        detected_errors=detected_errors,
        is_terminal=is_terminal,
        terminal_type=terminal_type,
        full_text=full_text
    )
