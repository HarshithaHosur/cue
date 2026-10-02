# ============================================================
#  SUPPORT PAGE ANALYZER — Real Multimodal Vision & OCR Engine
#  Truly analyzes the user's live screen using Gemini Vision &
#  structured EasyOCR geometry. Zero hardcoded responses.
# ============================================================

import os
import json
import re
import time
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from intent_platform.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from intent_platform.core.support.screen_context import ScreenContext

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class SupportPageAnalyzer:
    """
    Multimodal vision & scene analyzer.
    Combines live screen frames, EasyOCR spatial element coordinates,
    and Gemini 2.5 Flash Vision to deliver genuine, dynamic reasoning.
    """

    CANDIDATE_MODELS = [
        GEMINI_MODEL,
        "gemini-3.8-flash",
        "gemini-3.5-flash",
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY")
        self.client_ready = False
        self._init_gemini()

    def _init_gemini(self):
        # Refresh key from environment if changed
        if not self.api_key:
            self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if self.api_key and GENAI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.client_ready = True
            except Exception as e:
                print(f"[PageAnalyzer] genai configure note: {e}")
                self.client_ready = False

    def analyze(
        self,
        command: str,
        image_bytes: bytes,
        context: Dict[str, Any],
        res_w: int,
        res_h: int,
        screen_context: Optional[ScreenContext] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes the visible screen and user request.
        Priority:
        1. Live Gemini Vision reasoning over active screen + ScreenContext.
        2. Dynamic Screen Reasoning over live EasyOCR geometry & visible elements.
        Zero hardcoded templates.
        """
        self._init_gemini()

        # Format conversation history
        history_summary = ""
        if conversation_history:
            history_summary = "Recent Conversation History:\n" + "\n".join(
                f"- {item.get('role', 'user')}: {item.get('content', '')}"
                for item in conversation_history[-4:]
            )

        # ── 1. Gemini Vision Multimodal Reasoning ──
        if self.client_ready and self.api_key and image_bytes:
            ctx_summary = screen_context.to_dict() if screen_context else dict(context)
            if additional_context:
                ctx_summary["additional_runtime_context"] = additional_context
            system_instruction = f"""You are an Expert Multimodal AI Support Executive speaking to the user on a live audio call.
Screen Resolution: {res_w}x{res_h}
Live Screen Context: {json.dumps(ctx_summary, default=str)}
{history_summary}

ROLE & PERSONA:
You are an empathetic, highly skilled human support executive who can SEE the user's active screen, LISTEN to their voice, and help guide or automate tasks.
You assist across ANY website (Amazon, Meesho, Flipkart, Zomato, GitHub) and application (Terminal, VS Code, Browser).
NEVER use placeholder text or canned responses. Reason genuinely over what is ACTUALLY VISIBLE on the user's screen right now.

GUIDELINES:
1. Speak warmly and conversationally for earbud TTS audio. Avoid curt, robotic statements.
2. Explain what you observe on screen, which button or section you found, and why.
3. If the user asks to open cart, returns, or support, locate the exact coordinates of that button from visible_buttons or the visual image.
4. If an error is visible, explain the root cause and recommend the exact fix.
5. Provide both:
   - "explanation_text": Comprehensive, structured message for the UI conversation panel.
   - "explanation_voice": Warm, natural spoken response for voice TTS (2-3 natural sentences with follow-up guidance).

Analyze the visible screen, the user's spoken request: "{command}", and return valid JSON conforming to this schema:
{{
  "website": "string (e.g. Amazon, Meesho, GitHub, Terminal, etc.)",
  "page_type": "string (e.g. Home, Orders, Cart, Returns, Customer Support, Product Page, Checkout, Terminal)",
  "is_support_page": true|false,
  "user_intent": "string (e.g. Open Cart, Replace Product, Diagnose Git Error)",
  "reasoning_steps": [
    "👀 Detected <Website> <Page Type>",
    "🔍 Locating <Target Button/Element>",
    "✅ Found <Target> at (<X>, <Y>)",
    "🎯 Highlighting <Target>"
  ],
                "target_element": {{
    "found": true|false,
    "label": "string",
    "type": "button|link|input|card|menu|tab",
    "x": integer (center X 0 to {res_w}),
    "y": integer (center Y 0 to {res_h}),
    "w": integer (width in pixels),
    "h": integer (height in pixels),
    "confidence": float (0.0 to 1.0)
  }},
  "explanation_text": "string (professional chat response)",
  "explanation_voice": "string (natural spoken response)",
    "suggested_action": "click|highlight|scroll|explain|fill|select",
    "scroll_direction": "up|down|none",
  "risk_level": "SAFE|MEDIUM_RISK|HIGH_RISK",
  "requires_confirmation": true|false,
  "confirmation_prompt": "string (ask permission before action)",
  "workflow_completed": true|false
}}
Include "current_user_goal", "selected_item", "dialogs", and "warnings" when visible or inferable; use empty values when not applicable.
Never invent labels or coordinates. Coordinates are relative to the supplied screenshot. If the target is not clearly visible, set found=false and suggested_action="explain".
Return ONLY valid JSON. No markdown code blocks.
"""
            tried_models = set()
            for model_name in self.CANDIDATE_MODELS:
                if model_name in tried_models:
                    continue
                tried_models.add(model_name)
                try:
                    model = genai.GenerativeModel(
                        model_name=model_name,
                        system_instruction=system_instruction,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    response = model.generate_content([
                        f"User Request: {command}",
                        {"mime_type": "image/png", "data": image_bytes}
                    ])
                    if response and response.text:
                        raw = response.text.strip()
                        if raw.startswith("```json"):
                            raw = raw[7:]
                        if raw.startswith("```"):
                            raw = raw[3:]
                        if raw.endswith("```"):
                            raw = raw[:-3]
                        parsed = json.loads(raw.strip())
                        required_text = ("explanation_text", "explanation_voice", "suggested_action")
                        if not isinstance(parsed, dict) or any(
                            not isinstance(parsed.get(key), str) or not parsed[key].strip()
                            for key in required_text
                        ):
                            raise ValueError("Gemini returned an incomplete screen analysis")
                        if parsed["suggested_action"] not in {"click", "highlight", "scroll", "explain"}:
                            raise ValueError("Gemini returned an unsupported action")
                        return parsed
                except Exception as e:
                    print(f"[PageAnalyzer] Gemini model {model_name} failed ({type(e).__name__}).")

        raise RuntimeError("Gemini Vision is unavailable; screen-grounded analysis was not generated.")

    def _dynamic_screen_reasoning(
        self,
        command: str,
        screen_context: Optional[ScreenContext],
        fallback_context: Dict[str, Any],
        res_w: int,
        res_h: int,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        raise RuntimeError("Rule-based screen responses are disabled; use Gemini Vision analysis.")

        """
        Legacy response rules retained temporarily for migration reference.
        """
        cmd_lower = command.lower().strip()

        # Fallback fields if screen_context is not provided
        website = screen_context.website if screen_context else fallback_context.get("website", "General Application")
        page_type = screen_context.current_page if screen_context else fallback_context.get("page_type", "Standard Window")
        is_support = screen_context.is_support_page if screen_context else fallback_context.get("is_support_page", False)
        visible_buttons = screen_context.visible_buttons if screen_context else []
        ocr_lines = screen_context.ocr_lines if screen_context else []
        is_terminal = screen_context.is_terminal if screen_context else False
        terminal_type = screen_context.terminal_type if screen_context else "none"

        # ── CASE 1: Open Cart / View Cart ──
        if any(w in cmd_lower for w in ["open cart", "view cart", "my cart", "show cart", "check cart", "go to cart"]):
            cart_btn = None
            if screen_context:
                cart_btn = screen_context.find_button("cart") or screen_context.find_button("bag")

            if cart_btn:
                cx, cy = cart_btn["x"], cart_btn["y"]
                cw, ch = cart_btn["w"], cart_btn["h"]
                lbl = cart_btn["label"]
                return {
                    "website": website,
                    "page_type": page_type,
                    "is_support_page": False,
                    "user_intent": "Open Cart",
                    "reasoning_steps": [
                        f"👀 Detected {website} ({page_type})",
                        f"🔍 Locating Cart button in visible UI",
                        f"✅ Located '{lbl}' at ({cx}, {cy})",
                        f"🎯 Highlighting Cart button for your confirmation"
                    ],
                    "target_element": {
                        "found": True,
                        "label": lbl,
                        "type": "button",
                        "x": cx,
                        "y": cy,
                        "w": cw,
                        "h": ch,
                        "confidence": 0.95
                    },
                    "explanation_text": f"I've located your {lbl} button on {website} at ({cx}, {cy}). I've highlighted it for you. Shall I click to open your cart?",
                    "explanation_voice": f"I've found the Cart button on {website} and highlighted it for you. Would you like me to open it?",
                    "suggested_action": "click",
                    "risk_level": "MEDIUM_RISK",
                    "requires_confirmation": True,
                    "confirmation_prompt": "Would you like me to open your Cart?",
                    "workflow_completed": False
                }
            else:
                return {
                    "website": website,
                    "page_type": page_type,
                    "is_support_page": False,
                    "user_intent": "Open Cart",
                    "reasoning_steps": [
                        f"👀 Analyzing active window: {website}",
                        f"🔍 Scanning visible buttons for Cart or Bag",
                        f"⚠️ Cart button is not visible in the current viewport"
                    ],
                    "target_element": {"found": False},
                    "explanation_text": f"I'm looking at {website} ({page_type}), but the Cart button is not visible on your current screen. You may need to scroll up to the top navigation header.",
                    "explanation_voice": f"I'm looking at {website}, but I don't see the cart button on this screen right now. Try scrolling to the top navigation.",
                    "suggested_action": "scroll",
                    "risk_level": "SAFE",
                    "requires_confirmation": False,
                    "confirmation_prompt": "",
                    "workflow_completed": False
                }

        # ── CASE 2: Returns & Orders / Show Orders ──
        if any(w in cmd_lower for w in ["open returns", "returns & orders", "show my orders", "open orders", "my orders", "your orders"]):
            orders_btn = None
            if screen_context:
                orders_btn = (
                    screen_context.find_button("returns & orders") or
                    screen_context.find_button("your orders") or
                    screen_context.find_button("orders")
                )

            if orders_btn:
                cx, cy = orders_btn["x"], orders_btn["y"]
                lbl = orders_btn["label"]
                return {
                    "website": website,
                    "page_type": page_type,
                    "is_support_page": True,
                    "user_intent": "Open Returns & Orders",
                    "reasoning_steps": [
                        f"👀 Detected {website} ({page_type})",
                        f"🔍 Locating Returns & Orders navigation button",
                        f"✅ Found '{lbl}' at ({cx}, {cy})",
                        f"🎯 Highlighting '{lbl}'"
                    ],
                    "target_element": {
                        "found": True,
                        "label": lbl,
                        "type": "button",
                        "x": cx,
                        "y": cy,
                        "w": orders_btn["w"],
                        "h": orders_btn["h"],
                        "confidence": 0.95
                    },
                    "explanation_text": f"I located the '{lbl}' option on {website}. I've highlighted it on your screen. Shall I open your order history now?",
                    "explanation_voice": f"I found the Returns and Orders button on {website} and highlighted it. Shall I open it for you?",
                    "suggested_action": "click",
                    "risk_level": "MEDIUM_RISK",
                    "requires_confirmation": True,
                    "confirmation_prompt": f"Shall I click {lbl} to open your orders?",
                    "workflow_completed": False
                }
            else:
                return {
                    "website": website,
                    "page_type": page_type,
                    "is_support_page": False,
                    "user_intent": "Open Orders",
                    "reasoning_steps": [
                        f"👀 Scanning {website} for Orders navigation",
                        f"ℹ️ Currently on page: {page_type}"
                    ],
                    "target_element": {"found": False},
                    "explanation_text": f"I am looking at {website} on the {page_type} page. I don't see the Orders button in this section. Please make sure the header is visible.",
                    "explanation_voice": f"I don't see the orders button on this section of {website}. Try scrolling up to view the main header.",
                    "suggested_action": "explain",
                    "risk_level": "SAFE",
                    "requires_confirmation": False,
                    "confirmation_prompt": "",
                    "workflow_completed": False
                }

        # ── CASE 3: Customer Support / Help Requests ──
        if any(w in cmd_lower for w in ["customer support", "customer service", "help", "need help", "contact support"]):
            support_btn = None
            if screen_context:
                support_btn = (
                    screen_context.find_button("customer service") or
                    screen_context.find_button("help centre") or
                    screen_context.find_button("customer support") or
                    screen_context.find_button("help") or
                    screen_context.find_button("contact us")
                )

            if support_btn:
                cx, cy = support_btn["x"], support_btn["y"]
                lbl = support_btn["label"]
                return {
                    "website": website,
                    "page_type": "Customer Support",
                    "is_support_page": True,
                    "user_intent": "Open Customer Support",
                    "reasoning_steps": [
                        f"👀 Detected {website} interface",
                        f"🔍 Scanning for Customer Support options",
                        f"✅ Found '{lbl}' at ({cx}, {cy})",
                        f"🎯 Highlighting Customer Support button"
                    ],
                    "target_element": {
                        "found": True,
                        "label": lbl,
                        "type": "button",
                        "x": cx,
                        "y": cy,
                        "w": support_btn["w"],
                        "h": support_btn["h"],
                        "confidence": 0.95
                    },
                    "explanation_text": f"I located the '{lbl}' option on {website}. I've highlighted it for you. Would you like me to open customer support?",
                    "explanation_voice": f"I found the Customer Support button on {website} and highlighted it. Would you like me to open it?",
                    "suggested_action": "click",
                    "risk_level": "MEDIUM_RISK",
                    "requires_confirmation": True,
                    "confirmation_prompt": f"Shall I open {lbl} for you?",
                    "workflow_completed": False
                }

        # ── CASE 4: Wrong Product / Replace / Return / Delayed Refund ──
        if any(w in cmd_lower for w in ["wrong product", "replace", "return", "refund", "delayed", "not arrived", "damaged"]):
            replace_btn = None
            if screen_context:
                replace_btn = (
                    screen_context.find_button("return or replace") or
                    screen_context.find_button("return items") or
                    screen_context.find_button("replace items") or
                    screen_context.find_button("need help")
                )

            if replace_btn:
                cx, cy = replace_btn["x"], replace_btn["y"]
                lbl = replace_btn["label"]
                return {
                    "website": website,
                    "page_type": page_type,
                    "is_support_page": True,
                    "user_intent": "Replace / Return Item",
                    "reasoning_steps": [
                        f"👀 Identified {website} ({page_type})",
                        f"📦 Found eligible order on your screen",
                        f"🔍 Located resolution option: '{lbl}'",
                        f"🎯 Highlighting '{lbl}' button"
                    ],
                    "target_element": {
                        "found": True,
                        "label": lbl,
                        "type": "button",
                        "x": cx,
                        "y": cy,
                        "w": replace_btn["w"],
                        "h": replace_btn["h"],
                        "confidence": 0.96
                    },
                    "explanation_text": f"I see your order on {website}. I've located and highlighted the '{lbl}' option. Shall I click it to begin your replacement request?",
                    "explanation_voice": f"I found the return and replace option for your order on {website} and highlighted it. Shall I open the replacement form for you?",
                    "suggested_action": "click",
                    "risk_level": "MEDIUM_RISK",
                    "requires_confirmation": True,
                    "confirmation_prompt": f"Shall I click '{lbl}' to start the replacement request?",
                    "workflow_completed": False
                }
            elif page_type != "Orders":
                # Guide user to Orders page first
                orders_nav = screen_context.find_button("returns & orders") or screen_context.find_button("your orders") if screen_context else None
                if orders_nav:
                    cx, cy = orders_nav["x"], orders_nav["y"]
                    return {
                        "website": website,
                        "page_type": page_type,
                        "is_support_page": True,
                        "user_intent": "Navigate to Orders for Replacement",
                        "reasoning_steps": [
                            f"👀 Currently on {website} ({page_type})",
                            f"ℹ️ Order history is required to process wrong product replacement",
                            f"🔍 Located '{orders_nav['label']}' in header navigation",
                            f"🎯 Highlighting '{orders_nav['label']}'"
                        ],
                        "target_element": {
                            "found": True,
                            "label": orders_nav["label"],
                            "type": "button",
                            "x": cx,
                            "y": cy,
                            "w": orders_nav["w"],
                            "h": orders_nav["h"],
                            "confidence": 0.92
                        },
                        "explanation_text": f"To replace your order, we need to view your recent deliveries. I've highlighted the '{orders_nav['label']}' button in the top navigation. Shall I open it?",
                        "explanation_voice": f"To help you replace the wrong product, we need to open your orders. I've highlighted Returns and Orders for you. Shall I click it?",
                        "suggested_action": "click",
                        "risk_level": "MEDIUM_RISK",
                        "requires_confirmation": True,
                        "confirmation_prompt": "Shall I open your Returns & Orders page?",
                        "workflow_completed": False
                    }

        # ── CASE 5: Terminal & Code Diagnostics ──
        if is_terminal or any(w in cmd_lower for w in ["error", "git", "terminal", "traceback", "syntax", "fail"]):
            err_line = ""
            for line in ocr_lines:
                if any(k in line.lower() for k in ["fatal:", "error:", "traceback", "exception", "failed", "cannot find"]):
                    err_line = line.strip()
                    break

            if "not a git repository" in err_line.lower() or terminal_type == "git":
                return {
                    "website": "Git Terminal",
                    "page_type": "Terminal",
                    "is_support_page": True,
                    "user_intent": "Diagnose Git Error",
                    "reasoning_steps": [
                        "👀 Captured active terminal window",
                        "🔤 OCR detected: 'fatal: not a git repository'",
                        "🧠 Diagnosing: Current folder is not initialized as a Git repository root",
                        "💡 Solution: Change directory to the repository root or run git init"
                    ],
                    "target_element": {"found": False},
                    "explanation_text": "I analyzed your terminal. You received `fatal: not a git repository`. You are currently inside a folder that does not contain a `.git` root folder. Navigate to your project folder using `cd ..`, or initialize Git with `git init`.",
                    "explanation_voice": "You are currently inside a folder that is not the Git repository root. You can run 'cd ..' to move to the parent folder, or 'git init' if you want to initialize a new repository here. Would you like me to run 'cd ..' for you?",
                    "suggested_action": "explain",
                    "risk_level": "SAFE",
                    "requires_confirmation": False,
                    "confirmation_prompt": "",
                    "workflow_completed": True
                }

        # ── CASE 6: General Scene Understanding (True Screen-Derived Summary) ──
        top_headings = [l for l in ocr_lines if len(l.strip()) > 3][:3]
        headings_desc = f" I see '{', '.join(top_headings)}'." if top_headings else ""
        button_names = [b["label"] for b in visible_buttons[:4]]
        btn_desc = f" Visible actions include: {', '.join(button_names)}." if button_names else ""

        exp_text = f"I've analyzed your active window on {website} ({page_type}).{headings_desc}{btn_desc} How can I assist you with this page?"
        exp_voice = f"I'm looking at {website} on your screen.{headings_desc} How can I assist you?"

        return {
            "website": website,
            "page_type": page_type,
            "is_support_page": is_support,
            "user_intent": "General Screen Inquiry",
            "reasoning_steps": [
                f"👀 Captured active window: {website}",
                f"📄 Classified current page as: {page_type}",
                f"🔤 Extracted {len(ocr_lines)} text lines via OCR",
                f"🔘 Detected {len(visible_buttons)} interactive elements on screen"
            ],
            "target_element": visible_buttons[0] if visible_buttons else {"found": False},
            "explanation_text": exp_text,
            "explanation_voice": exp_voice,
            "suggested_action": "explain",
            "risk_level": "SAFE",
            "requires_confirmation": False,
            "confirmation_prompt": "",
            "workflow_completed": True
        }
