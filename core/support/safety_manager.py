# ============================================================
#  SAFETY MANAGER & RISK CLASSIFIER — Permission-Based Automation
#  Enforces strict safety guardrails for customer support workflows:
#  Safe (Execute immediately), Medium Risk (Ask once), High Risk (Always ask).
# ============================================================

from enum import Enum
from typing import Dict, Any, Optional, Tuple


class ActionRiskLevel(Enum):
    SAFE = "SAFE"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"


class SafetyManager:
    """
    Evaluates actions against safety policies.
    Guarantees the AI never performs sensitive or destructive operations silently.
    """

    SAFE_ACTION_KEYWORDS = [
        'highlight', 'explain', 'read', 'scroll', 'scroll down', 'scroll up',
        'zoom', 'zoom in', 'zoom out', 'view', 'inspect', 'show', 'summarize'
    ]

    MEDIUM_RISK_KEYWORDS = [
        'continue', 'next', 'navigate', 'fill', 'input', 'select reason',
        'choose option', 'proceed', 'open support', 'contact support', 'open ticket'
    ]

    HIGH_RISK_KEYWORDS = [
        'submit refund', 'request refund', 'claim refund',
        'submit replacement', 'replace order', 'replace product', 'confirm replacement',
        'cancel order', 'cancel booking', 'cancel flight', 'abort order',
        'confirm payment', 'pay now', 'transfer funds', 'authorize payment',
        'delete account', 'remove account', 'delete data', 'close account',
        'send complaint', 'file complaint', 'escalate dispute', 'submit claim'
    ]

    def __init__(self):
        self.pending_action: Optional[Dict[str, Any]] = None

    def classify_action(self, action_type: str, action_label: str = "", target_text: str = "") -> Tuple[ActionRiskLevel, str]:
        """
        Classifies the action risk level and provides the reason.
        """
        text = f"{action_type} {action_label} {target_text}".lower().strip()

        # Check High Risk first
        for kw in self.HIGH_RISK_KEYWORDS:
            if kw in text:
                return (
                    ActionRiskLevel.HIGH_RISK,
                    f"Action involves sensitive financial, cancellation, or submission action ('{kw}')."
                )

        # High-risk button label triggers
        if any(w in text for w in ['submit', 'confirm and place', 'pay', 'cancel order', 'delete', 'finalize refund']):
            return (
                ActionRiskLevel.HIGH_RISK,
                "Action submits or permanently alters user order, payment, or account state."
            )

        # Check Medium Risk
        for kw in self.MEDIUM_RISK_KEYWORDS:
            if kw in text:
                return (
                    ActionRiskLevel.MEDIUM_RISK,
                    f"Action advances workflow or modifies form data ('{kw}')."
                )

        if any(w in text for w in ['click', 'select', 'press', 'tap', 'fill', 'enter']):
            return (
                ActionRiskLevel.MEDIUM_RISK,
                "Interactive UI action requires single confirmation."
            )

        # Default to Safe
        return (
            ActionRiskLevel.SAFE,
            "Non-destructive informational or navigation action."
        )

    def prepare_action(
        self,
        action_name: str,
        target_coords: Optional[Tuple[int, int]] = None,
        target_label: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepares an action, evaluates risk, and formats the user confirmation prompt if required.
        """
        risk_level, reason = self.classify_action(action_name, target_label)
        details = details or {}

        if action_name in {"click", "fill", "select"} and target_coords is None:
            risk_level = ActionRiskLevel.HIGH_RISK
            reason = "Interactive action has no verified visible target; automation is blocked."

        requires_confirmation = (risk_level in [ActionRiskLevel.MEDIUM_RISK, ActionRiskLevel.HIGH_RISK])

        confirmation_prompt = ""
        if risk_level == ActionRiskLevel.HIGH_RISK:
            confirmation_prompt = f"This will perform a sensitive action: {target_label or action_name}. Would you like me to continue?"
        elif risk_level == ActionRiskLevel.MEDIUM_RISK:
            confirmation_prompt = f"I've highlighted the option '{target_label}'. Should I click it to continue?"

        action_payload = {
            "action_name": action_name,
            "target_label": target_label,
            "target_coords": target_coords,
            "risk_level": risk_level.value,
            "risk_reason": reason,
            "requires_confirmation": requires_confirmation,
            "confirmation_prompt": confirmation_prompt,
            "details": details
        }

        if requires_confirmation:
            self.pending_action = action_payload
        else:
            self.pending_action = None

        return action_payload

    def has_pending_action(self) -> bool:
        return self.pending_action is not None

    def pop_pending_action(self) -> Optional[Dict[str, Any]]:
        action = self.pending_action
        self.pending_action = None
        return action

    def cancel_pending_action(self) -> Optional[Dict[str, Any]]:
        cancelled = self.pending_action
        self.pending_action = None
        return cancelled
