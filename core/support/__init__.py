# ============================================================
#  SUPPORT MODULE — AI Customer Support Executive
# ============================================================

from intent_platform.core.support.screen_capture import EventDrivenScreenCapture
from intent_platform.core.support.context_detector import SupportContextDetector
from intent_platform.core.support.safety_manager import SafetyManager, ActionRiskLevel
from intent_platform.core.support.highlighter import (
    VisualHighlightOverlay,
    highlight_element,
    clear_highlight,
    initialize_highlighter
)
from intent_platform.core.support.audit_logger import SupportAuditLogger, global_audit_logger
from intent_platform.core.support.page_analyzer import SupportPageAnalyzer
from intent_platform.core.support.support_agent import (
    CustomerSupportAgent,
    CustomerSupportAgentSignals,
    get_support_agent
)

__all__ = [
    "EventDrivenScreenCapture",
    "SupportContextDetector",
    "SafetyManager",
    "ActionRiskLevel",
    "VisualHighlightOverlay",
    "highlight_element",
    "clear_highlight",
    "initialize_highlighter",
    "SupportAuditLogger",
    "global_audit_logger",
    "SupportPageAnalyzer",
    "CustomerSupportAgent",
    "CustomerSupportAgentSignals",
    "get_support_agent",
]
