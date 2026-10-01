# ============================================================
#  SUPPORT CONTEXT DETECTOR — Web & Application Intelligence
#  Automatically determines active application, browser, website,
#  page type, and triggers Support Detection Mode.
# ============================================================

import re
import sys
from typing import Dict, Any, Optional

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

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


class SupportContextDetector:
    """
    Website-agnostic context detector.
    Analyzes active window, process hierarchy, and browser titles to classify
    current website, page type, and support status.
    """

    KNOWN_BROWSERS = {
        'chrome.exe': 'Google Chrome',
        'msedge.exe': 'Microsoft Edge',
        'firefox.exe': 'Mozilla Firefox',
        'brave.exe': 'Brave Browser',
        'opera.exe': 'Opera',
        'arc.exe': 'Arc Browser',
        'vivaldi.exe': 'Vivaldi'
    }

    KNOWN_WEBSITES = [
        # E-Commerce
        ('amazon', 'Amazon', '🛒'),
        ('flipkart', 'Flipkart', '🛍️'),
        ('myntra', 'Myntra', '👗'),
        ('ajio', 'Ajio', '👔'),
        ('ebay', 'eBay', '📦'),
        ('meesho', 'Meesho', '📦'),
        # Food & Delivery
        ('zomato', 'Zomato', '🍕'),
        ('swiggy', 'Swiggy', '🍔'),
        ('blinkit', 'Blinkit', '🥦'),
        ('zepto', 'Zepto', '⚡'),
        ('ubereats', 'Uber Eats', '🥡'),
        # Banking & Finance
        ('hdfc', 'HDFC Bank', '🏦'),
        ('icici', 'ICICI Bank', '🏦'),
        ('sbi', 'State Bank of India', '🏦'),
        ('axis', 'Axis Bank', '🏦'),
        ('chase', 'Chase Bank', '🏦'),
        ('bankofamerica', 'Bank of America', '🏦'),
        ('paypal', 'PayPal', '💳'),
        ('zerodha', 'Zerodha', '📈'),
        ('groww', 'Groww', '🌱'),
        # Travel & Airlines
        ('airindia', 'Air India', '✈️'),
        ('indigo', 'IndiGo Airlines', '✈️'),
        ('emirates', 'Emirates', '✈️'),
        ('makemytrip', 'MakeMyTrip', '🏖️'),
        ('irctc', 'IRCTC Rail', '🚆'),
        ('booking.com', 'Booking.com', '🏨'),
        # Insurance & Healthcare
        ('starhealth', 'Star Health Insurance', '🛡️'),
        ('lic', 'LIC Insurance', '🛡️'),
        ('policybazaar', 'PolicyBazaar', '📑'),
        ('apollo', 'Apollo 24|7', '🏥'),
        ('practo', 'Practo', '🩺'),
        # University & Portals
        ('canvas', 'Canvas Portal', '🎓'),
        ('blackboard', 'Blackboard', '📚'),
        ('coursera', 'Coursera', '🎓'),
        ('nptel', 'NPTEL', '📖'),
        ('service-now', 'ServiceNow Portal', '💼'),
        ('jira', 'Jira Service Management', '🎫'),
        ('zendesk', 'Zendesk Support', '🎧'),
        ('gov.in', 'Government Service Portal', '🏛️')
    ]

    SUPPORT_KEYWORDS = [
        'support', 'help', 'returns', 'return', 'refund', 'refunds',
        'complaint', 'contact us', 'customer service', 'customer care',
        'resolution', 'dispute', 'issue', 'ticket', 'claim', 'claims',
        'grievance', 'assistance', 'order help', 'delivery support'
    ]

    PAGE_TYPE_RULES = [
        # (Keywords in title/url, Page Type)
        (['order', 'your orders', 'order history', 'orders'], 'Orders Page'),
        (['track', 'tracking', 'order status', 'delivery status'], 'Current Order Tracking'),
        (['return', 'replace', 'replacement', 'exchange'], 'Returns & Replacement'),
        (['refund', 'refund status'], 'Refunds & Reimbursements'),
        (['statement', 'e-statement', 'transaction', 'passbook', 'account balance'], 'Statements Page'),
        (['claim', 'file claim', 'claim status', 'insurance claim'], 'Claim Form'),
        (['cart', 'basket', 'bag'], 'Cart Page'),
        (['checkout', 'payment', 'billing'], 'Checkout Page'),
        (['flight', 'boarding pass', 'web check-in', 'seat selection'], 'Flight Management'),
        (['help center', 'customer support', 'contact us', 'support', 'faq'], 'Support & Help Desk'),
        (['login', 'sign in', 'authenticate'], 'Authentication Page'),
        (['profile', 'account settings', 'security'], 'Account Settings')
    ]

    @classmethod
    def get_active_window_info(cls) -> Dict[str, Any]:
        """Inspects currently focused window via win32 and psutil."""
        title = ""
        app_name = "Desktop"
        browser_name = None
        pid = None

        if WIN32_AVAILABLE and sys.platform == 'win32':
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd).strip()
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid and PSUTIL_AVAILABLE:
                        try:
                            proc = psutil.Process(pid)
                            proc_name = proc.name().lower()
                            if proc_name in cls.KNOWN_BROWSERS:
                                browser_name = cls.KNOWN_BROWSERS[proc_name]
                                app_name = browser_name
                            else:
                                app_name = proc.name()
                        except Exception:
                            pass
            except Exception:
                pass

        if not title and GW_AVAILABLE:
            try:
                active = gw.getActiveWindow()
                if active and active.title:
                    title = active.title.strip()
            except Exception:
                pass

        return {
            "title": title,
            "title_lower": title.lower(),
            "app_name": app_name,
            "browser_name": browser_name,
            "is_browser": browser_name is not None
        }

    @classmethod
    def detect_context(cls) -> Dict[str, Any]:
        """
        Determines current Application, Browser, Website, Page Type,
        and whether it qualifies as a Customer Support page.
        """
        info = cls.get_active_window_info()
        title_lower = info["title_lower"]

        # 1. Determine Website
        detected_website = "General Website"
        website_icon = "🌐"
        for kw, name, icon in cls.KNOWN_WEBSITES:
            if kw in title_lower:
                detected_website = name
                website_icon = icon
                break

        # 2. Determine Page Type
        detected_page_type = "Standard Webpage"
        for keywords, p_type in cls.PAGE_TYPE_RULES:
            if any(k in title_lower for k in keywords):
                detected_page_type = p_type
                break

        # 3. Support Detection Mode
        is_support_page = any(k in title_lower for k in cls.SUPPORT_KEYWORDS)

        proactive_msg_text = ""
        proactive_msg_voice = ""
        if is_support_page:
            proactive_msg_text = "I noticed you're on a customer support page. I can help you navigate it."
            proactive_msg_voice = "It looks like you're on a customer support page. Let me know how I can assist you."

        return {
            "raw_title": info["title"],
            "application": info["app_name"],
            "browser": info["browser_name"] or "None (Desktop App)",
            "is_browser": info["is_browser"],
            "website": detected_website,
            "website_icon": website_icon,
            "page_type": detected_page_type,
            "is_support_page": is_support_page,
            "proactive_text": proactive_msg_text,
            "proactive_voice": proactive_msg_voice
        }
