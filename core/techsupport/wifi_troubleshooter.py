# ============================================================
#  MODULE 3: WIFI TROUBLESHOOTING
#  Real-time network diagnostic engine.
#  Inspects Wi-Fi adapter, SSID, signal strength, IP gateway,
#  DNS resolution, and internet ping.
#  Enforces strict permission gates before opening settings or
#  flushing DNS / resetting network adapter.
# ============================================================

import os
import re
import socket
import subprocess
import time
from typing import Dict, Any, List, Optional
import psutil

from intent_platform.core.support.audit_logger import global_audit_logger


class WiFiTroubleshooter:
    """
    Module 3: Wi-Fi & Network Diagnostics Executive.
    Diagnoses connectivity barriers, checks hardware states,
    and guides remediation with permission safeguards.
    """

    def __init__(self):
        self.audit_logger = global_audit_logger

    def run_diagnostics(self) -> Dict[str, Any]:
        """
        Executes a complete 5-point Wi-Fi diagnostic inspection:
        1. Adapter Status & Wi-Fi Enabled State
        2. Connected SSID & Signal Strength
        3. Local IP & Gateway
        4. Internet Ping & Latency (8.8.8.8)
        5. DNS Resolution (google.com)
        """
        start_time = time.time()
        self.audit_logger.log(
            "Wi-Fi diagnostics initiated. Probing interfaces and internet reachability...",
            category="WIFI_DIAG",
            risk_level="INFO"
        )

        # 1. Interface & Signal details from netsh
        wlan_info = self._get_netsh_wlan_info()

        # 2. Check if Wi-Fi adapter exists and is enabled
        wifi_enabled = wlan_info.get("has_wifi_adapter", False)
        adapter_state = wlan_info.get("state", "disconnected")
        ssid = wlan_info.get("ssid", "None")
        signal = wlan_info.get("signal", "0%")
        signal_pct = wlan_info.get("signal_pct", 0)
        radio_type = wlan_info.get("radio_type", "Unknown")

        # 3. Test Internet Connectivity (Socket check to 8.8.8.8:53)
        internet_connected, ping_ms = self._check_internet_reachability()

        # 4. Test DNS Resolution
        dns_ok = self._check_dns_resolution()

        # 5. Formulate Diagnostic Assessment
        diagnosis_state = "HEALTHY"
        issues: List[str] = []
        fixes: List[str] = []
        suggested_action = "open_settings"
        action_label = "Open Network Settings"

        if not wifi_enabled:
            diagnosis_state = "NO_ADAPTER"
            issues.append("No active Wi-Fi adapter detected or Wi-Fi radio is switched off.")
            fixes.append("Turn on Wi-Fi in Windows Settings or enable the Wi-Fi physical switch.")
            suggested_action = "open_network_settings"
            action_label = "Open Wi-Fi Settings"
        elif adapter_state == "disconnected":
            diagnosis_state = "DISCONNECTED"
            issues.append("Wi-Fi is enabled, but not connected to any network.")
            fixes.append("Select an available network and enter the security passphrase.")
            suggested_action = "open_network_settings"
            action_label = "Open Available Networks"
        elif not internet_connected:
            diagnosis_state = "NO_INTERNET"
            issues.append(f"Connected to '{ssid}', but cannot reach external internet servers (No Internet Access).")
            fixes.append("Flush DNS cache and renew local IP address, or reboot the wireless router.")
            suggested_action = "flush_dns"
            action_label = "Flush DNS & Renew IP"
        elif not dns_ok:
            diagnosis_state = "DNS_FAILURE"
            issues.append("Internet is reachable via IP, but domain names cannot be resolved (DNS failure).")
            fixes.append("Flush DNS resolver cache or switch DNS to Google (8.8.8.8) or Cloudflare (1.1.1.1).")
            suggested_action = "flush_dns"
            action_label = "Flush DNS Cache"
        elif signal_pct > 0 and signal_pct < 35:
            diagnosis_state = "WEAK_SIGNAL"
            issues.append(f"Connected to '{ssid}' with weak signal strength ({signal}). Expect packet loss.")
            fixes.append("Move closer to the Wi-Fi access point or switch to 2.4GHz for wider coverage.")
            suggested_action = "none"
            action_label = "Signal Optimization"
        else:
            diagnosis_state = "OPTIMAL"
            issues.append("All network checks passed. Connection is healthy and stable.")
            fixes.append("No remediation needed.")
            suggested_action = "none"
            action_label = "Connection Healthy"

        # 6. Formulate Voice and Text Responses
        explanation_text, explanation_voice, confirmation_prompt = self._build_report(
            diagnosis_state=diagnosis_state,
            ssid=ssid,
            signal=signal,
            internet_connected=internet_connected,
            ping_ms=ping_ms,
            dns_ok=dns_ok,
            issues=issues,
            fixes=fixes,
            action_label=action_label
        )

        elapsed = round(time.time() - start_time, 2)
        self.audit_logger.log(
            f"Wi-Fi diagnostics completed in {elapsed}s: State={diagnosis_state}, SSID='{ssid}', Signal={signal}",
            category="WIFI_DIAG",
            risk_level="INFO"
        )

        return {
            "status": diagnosis_state,
            "wifi_enabled": wifi_enabled,
            "adapter_state": adapter_state,
            "ssid": ssid,
            "signal": signal,
            "signal_pct": signal_pct,
            "radio_type": radio_type,
            "internet_connected": internet_connected,
            "latency_ms": ping_ms,
            "dns_working": dns_ok,
            "issues": issues,
            "fixes": fixes,
            "suggested_action": suggested_action,
            "action_label": action_label,
            "explanation_text": explanation_text,
            "explanation_voice": explanation_voice,
            "confirmation_prompt": confirmation_prompt,
            "requires_confirmation": (suggested_action != "none")
        }

    def _get_netsh_wlan_info(self) -> Dict[str, Any]:
        """Parses Windows netsh wlan show interfaces output."""
        info = {
            "has_wifi_adapter": False,
            "state": "disconnected",
            "ssid": "None",
            "signal": "0%",
            "signal_pct": 0,
            "radio_type": "Unknown",
            "name": "Wi-Fi"
        }
        try:
            out = subprocess.check_output(
                "netsh wlan show interfaces",
                shell=True,
                text=True,
                stderr=subprocess.DEVNULL
            )
            if "There is 1 interface" in out or "interfaces on the system" in out or "Name" in out:
                info["has_wifi_adapter"] = True

            for line in out.splitlines():
                line = line.strip()
                if line.startswith("State"):
                    val = line.split(":", 1)[1].strip()
                    info["state"] = val
                elif line.startswith("SSID") and not line.startswith("BSSID"):
                    val = line.split(":", 1)[1].strip()
                    info["ssid"] = val
                elif line.startswith("Signal"):
                    val = line.split(":", 1)[1].strip()
                    info["signal"] = val
                    pct_match = re.search(r"(\d+)%", val)
                    if pct_match:
                        info["signal_pct"] = int(pct_match.group(1))
                elif line.startswith("Radio type"):
                    info["radio_type"] = line.split(":", 1)[1].strip()
                elif line.startswith("Name"):
                    info["name"] = line.split(":", 1)[1].strip()
        except Exception:
            # Fallback to psutil network interfaces
            nics = psutil.net_if_stats()
            for nic_name, nic_stat in nics.items():
                if "wi-fi" in nic_name.lower() or "wlan" in nic_name.lower() or "wireless" in nic_name.lower():
                    info["has_wifi_adapter"] = True
                    info["state"] = "connected" if nic_stat.isup else "disconnected"
                    info["name"] = nic_name
                    break

        return info

    def _check_internet_reachability(self) -> (bool, float):
        """Checks socket connectivity to Public DNS 8.8.8.8 port 53."""
        start = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.5)
            sock.connect(("8.8.8.8", 53))
            sock.close()
            latency = round((time.time() - start) * 1000, 1)
            return True, latency
        except Exception:
            return False, -1.0

    def _check_dns_resolution(self) -> bool:
        """Verifies domain name resolution works."""
        try:
            socket.gethostbyname("google.com")
            return True
        except Exception:
            return False

    def _build_report(
        self,
        diagnosis_state: str,
        ssid: str,
        signal: str,
        internet_connected: bool,
        ping_ms: float,
        dns_ok: bool,
        issues: List[str],
        fixes: List[str],
        action_label: str
    ) -> (str, str, str):
        """Generates detailed text, natural speech, and confirmation prompt."""
        status_icon = "🟢" if diagnosis_state == "OPTIMAL" else ("🟡" if diagnosis_state == "WEAK_SIGNAL" else "🔴")

        text = (
            f"📶 **Wi-Fi Diagnostics Report** {status_icon}\n\n"
            f"• **Network Status:** {diagnosis_state.replace('_', ' ')}\n"
            f"• **Connected Network (SSID):** `{ssid}`\n"
            f"• **Signal Strength:** {signal}\n"
            f"• **Internet Connectivity:** {'Online (' + str(ping_ms) + ' ms)' if internet_connected else 'Offline / No Route'}\n"
            f"• **DNS Status:** {'Operational' if dns_ok else 'Unresolvable'}\n\n"
            f"🔍 **Identified Issues:**\n" + "\n".join(f"- {iss}" for iss in issues) + "\n\n"
            f"🛠 **Recommended Actions:**\n" + "\n".join(f"- {fx}" for fx in fixes)
        )

        if diagnosis_state == "NO_INTERNET":
            voice = f"I detected that Wi-Fi is connected to {ssid}, but there is no internet connection. Would you like me to flush the DNS cache and renew your network settings?"
            confirm = "Flush DNS and renew IP configuration?"
        elif diagnosis_state == "DISCONNECTED":
            voice = "Your Wi-Fi adapter is turned on, but you are not connected to any network. Would you like me to open Network Settings?"
            confirm = "Open Windows Network Settings to select a Wi-Fi network?"
        elif diagnosis_state == "NO_ADAPTER":
            voice = "I found that your Wi-Fi is disabled or no wireless adapter was detected. Would you like me to open Network Settings?"
            confirm = "Open Windows Network Settings?"
        elif diagnosis_state == "WEAK_SIGNAL":
            voice = f"You are connected to {ssid}, but the Wi-Fi signal is weak at {signal}. Moving closer to your router is recommended."
            confirm = ""
        else:
            voice = f"Your Wi-Fi connection to {ssid} is healthy with strong signal at {signal} and {ping_ms} milliseconds latency."
            confirm = ""

        return text, voice, confirm

    def execute_fix(self, action_name: str) -> Dict[str, Any]:
        """
        Executes approved network remediation action.
        """
        self.audit_logger.log(
            f"Executing Wi-Fi remediation: {action_name}",
            category="WIFI_DIAG",
            risk_level="MEDIUM_RISK"
        )

        if action_name in ["flush_dns", "renew_ip"]:
            try:
                subprocess.run("ipconfig /flushdns", shell=True, check=True, capture_output=True)
                subprocess.run("ipconfig /renew", shell=True, capture_output=True, timeout=10)
                self.audit_logger.log("Flushed DNS and renewed IP configuration successfully", category="WIFI_DIAG", risk_level="SAFE")
                return {
                    "success": True,
                    "message": "Successfully flushed DNS resolver cache and renewed network lease."
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif action_name in ["open_settings", "open_network_settings"]:
            try:
                subprocess.Popen("start ms-settings:network-wifi", shell=True)
                return {"success": True, "message": "Opened Windows Wi-Fi Settings."}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unknown remediation action: {action_name}"}
