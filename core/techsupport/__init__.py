# ============================================================
#  CORE TECH SUPPORT PACKAGE — AI Technical Support Executive
# ============================================================

from intent_platform.core.techsupport.software_installer import (
    SoftwareInstallationAssistant,
    SOFTWARE_CATALOG
)
from intent_platform.core.techsupport.terminal_diagnostics import (
    TerminalErrorDiagnostics
)
from intent_platform.core.techsupport.wifi_troubleshooter import (
    WiFiTroubleshooter
)
from intent_platform.core.techsupport.battery_health import (
    BatteryHealthAssistant
)
from intent_platform.core.techsupport.tech_support_agent import (
    TechnicalSupportAgent
)

__all__ = [
    "SoftwareInstallationAssistant",
    "SOFTWARE_CATALOG",
    "TerminalErrorDiagnostics",
    "WiFiTroubleshooter",
    "BatteryHealthAssistant",
    "TechnicalSupportAgent"
]
