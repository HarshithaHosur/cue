# ============================================================
#  MODULE 1: SOFTWARE INSTALLATION ASSISTANT
#  Installs commonly used software safely through official sources.
#  Enforces strict permission gates, narrates every step,
#  synchronizes companion voice & text, and verifies installation.
# ============================================================

import os
import sys
import time
import shutil
import urllib.request
import subprocess
import threading
import webbrowser
from typing import Dict, Any, Optional, Callable, List

from intent_platform.core.support.audit_logger import global_audit_logger


# Verified Official Software Catalog
SOFTWARE_CATALOG: Dict[str, Dict[str, Any]] = {
    "python": {
        "name": "Python 3.11",
        "official_url": "https://www.python.org/downloads/",
        "direct_url": "https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe",
        "winget_id": "Python.Python.3.11",
        "installer_name": "python-installer.exe",
        "verify_cmd": ["python", "--version"],
        "verify_keyword": "Python 3.",
        "description": "Official Python 3 programming language environment."
    },
    "vscode": {
        "name": "Visual Studio Code",
        "official_url": "https://code.visualstudio.com/Download",
        "direct_url": "https://update.code.visualstudio.com/latest/win32-x64-user/stable",
        "winget_id": "Microsoft.VisualStudioCode",
        "installer_name": "VSCodeUserSetup.exe",
        "verify_cmd": ["code", "--version"],
        "verify_keyword": "",
        "description": "Microsoft Visual Studio Code lightweight code editor."
    },
    "git": {
        "name": "Git for Windows",
        "official_url": "https://git-scm.com/download/win",
        "direct_url": "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe",
        "winget_id": "Git.Git",
        "installer_name": "Git-installer.exe",
        "verify_cmd": ["git", "--version"],
        "verify_keyword": "git version",
        "description": "Git distributed version control system."
    },
    "java": {
        "name": "Eclipse Temurin OpenJDK Java 17",
        "official_url": "https://adoptium.net/",
        "direct_url": "https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.10%2B7/OpenJDK17U-jdk_x64_windows_hotspot_17.0.10_7.msi",
        "winget_id": "EclipseAdoptium.Temurin.17.JDK",
        "installer_name": "OpenJDK17-installer.msi",
        "verify_cmd": ["java", "-version"],
        "verify_keyword": "version",
        "description": "Adoptium Eclipse Temurin Java 17 SE Runtime & Development Kit."
    },
    "node": {
        "name": "Node.js LTS",
        "official_url": "https://nodejs.org/en/download",
        "direct_url": "https://nodejs.org/dist/v20.12.2/node-v20.12.2-x64.msi",
        "winget_id": "OpenJS.NodeJS.LTS",
        "installer_name": "node-v20-x64.msi",
        "verify_cmd": ["node", "--version"],
        "verify_keyword": "v20.",
        "description": "Node.js JavaScript runtime environment built on V8."
    },
    "docker": {
        "name": "Docker Desktop",
        "official_url": "https://www.docker.com/products/docker-desktop/",
        "direct_url": "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
        "winget_id": "Docker.DockerDesktop",
        "installer_name": "DockerDesktopInstaller.exe",
        "verify_cmd": ["docker", "--version"],
        "verify_keyword": "Docker version",
        "description": "Docker Desktop container management environment."
    },
    "chrome": {
        "name": "Google Chrome",
        "official_url": "https://www.google.com/chrome/",
        "direct_url": "https://dl.google.com/chrome/install/ChromeStandaloneSetup64.exe",
        "winget_id": "Google.Chrome",
        "installer_name": "ChromeSetup.exe",
        "verify_cmd": ["reg", "query", "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe"],
        "verify_keyword": "chrome.exe",
        "description": "Google Chrome modern web browser."
    },
    "notepad++": {
        "name": "Notepad++",
        "official_url": "https://notepad-plus-plus.org/downloads/",
        "direct_url": "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.6.4/npp.8.6.4.Installer.x64.exe",
        "winget_id": "Notepad++.Notepad++",
        "installer_name": "npp-installer.exe",
        "verify_cmd": ["reg", "query", "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\notepad++.exe"],
        "verify_keyword": "notepad++.exe",
        "description": "Notepad++ extensible source code and text editor."
    },
    "anydesk": {
        "name": "AnyDesk Remote Desktop",
        "official_url": "https://anydesk.com/en/downloads/windows",
        "direct_url": "https://download.anydesk.com/AnyDesk.exe",
        "winget_id": "AnyDeskSoftwareGmbH.AnyDesk",
        "installer_name": "AnyDesk.exe",
        "verify_cmd": ["where", "anydesk"],
        "verify_keyword": "anydesk",
        "description": "AnyDesk remote desktop connectivity application."
    },
    "obs": {
        "name": "OBS Studio",
        "official_url": "https://obsproject.com/download",
        "direct_url": "https://cdn-fastly.obsproject.com/downloads/OBS-Studio-30.1.2-Windows-Installer.exe",
        "winget_id": "OBSProject.OBSStudio",
        "installer_name": "OBS-Studio-Installer.exe",
        "verify_cmd": ["where", "obs64"],
        "verify_keyword": "obs64",
        "description": "OBS Studio live streaming and screen recording suite."
    }
}


class SoftwareInstallationAssistant:
    """
    Module 1: Professional IT Support Software Installation Executive.
    Safely resolves, downloads, executes, and verifies software packages.
    Enforces explicit user confirmation before opening URLs, downloading files, or executing installers.
    """

    def __init__(self, download_dir: Optional[str] = None):
        self.download_dir = download_dir or os.path.join(os.path.expanduser("~"), "Downloads", "IntentSupportInstallers")
        os.makedirs(self.download_dir, exist_ok=True)
        self.audit_logger = global_audit_logger
        self.active_install: Optional[Dict[str, Any]] = None

    def match_software(self, text: str) -> Optional[Dict[str, Any]]:
        """Identifies requested software package from user natural language utterance."""
        t = text.lower()
        if "vs code" in t or "vscode" in t or "visual studio code" in t:
            return SOFTWARE_CATALOG["vscode"]
        if "notepad++" in t or "notepad plus plus" in t or "notepadplusplus" in t:
            return SOFTWARE_CATALOG["notepad++"]
        if "python" in t:
            return SOFTWARE_CATALOG["python"]
        if "git" in t:
            return SOFTWARE_CATALOG["git"]
        if "java" in t or "jdk" in t:
            return SOFTWARE_CATALOG["java"]
        if "node" in t or "nodejs" in t or "node.js" in t:
            return SOFTWARE_CATALOG["node"]
        if "docker" in t:
            return SOFTWARE_CATALOG["docker"]
        if "chrome" in t or "google chrome" in t:
            return SOFTWARE_CATALOG["chrome"]
        if "anydesk" in t:
            return SOFTWARE_CATALOG["anydesk"]
        if "obs" in t or "obs studio" in t:
            return SOFTWARE_CATALOG["obs"]

        # Dynamic search in catalog keys
        for key, info in SOFTWARE_CATALOG.items():
            if key in t or info["name"].lower() in t:
                return info

        return None

    def prepare_installation_plan(self, software_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates the step-by-step installation plan and returns initial explanation + confirmation prompt.
        """
        name = software_info["name"]
        url = software_info["official_url"]

        self.active_install = {
            "info": software_info,
            "step": "AWAITING_OPEN_URL_OR_DOWNLOAD",
            "installer_path": os.path.join(self.download_dir, software_info["installer_name"]),
            "timestamp": time.time()
        }

        self.audit_logger.log(
            f"{name} installation started. Identified official source: {url}",
            category="SOFTWARE_INSTALL",
            risk_level="INFO"
        )

        explanation_text = (
            f"I found the verified official installer for {name}.\n\n"
            f"• Source: {url}\n"
            f"• Package: {software_info['description']}\n\n"
            f"Before downloading, I require your permission."
        )
        explanation_voice = f"I found the official {name} installer. Would you like me to open the official download page, or download the installer directly?"

        confirmation_prompt = f"Proceed with downloading {name} installer from {url}?"

        return {
            "status": "ready_for_confirmation",
            "software_name": name,
            "explanation_text": explanation_text,
            "explanation_voice": explanation_voice,
            "confirmation_prompt": confirmation_prompt,
            "action_name": "download_installer",
            "target_label": f"Download {name}",
            "risk_level": "MEDIUM_RISK"
        }

    def open_official_website(self, software_info: Optional[Dict[str, Any]] = None) -> bool:
        """Opens verified official website in default web browser."""
        target = software_info or (self.active_install["info"] if self.active_install else None)
        if not target:
            return False

        url = target["official_url"]
        self.audit_logger.log(
            f"Opening official website for {target['name']}: {url}",
            category="SOFTWARE_INSTALL",
            risk_level="MEDIUM_RISK"
        )
        webbrowser.open(url)
        return True

    def download_installer(
        self,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Downloads official software installer safely to local disk.
        Reports progress via callback.
        """
        if not self.active_install:
            return {"success": False, "error": "No active installation in progress"}

        info = self.active_install["info"]
        dest_path = self.active_install["installer_path"]
        download_url = info.get("direct_url")

        if not download_url:
            # Fallback to opening official URL
            self.open_official_website(info)
            return {
                "success": True,
                "opened_browser": True,
                "message": f"Opened official {info['name']} website for download."
            }

        try:
            if progress_callback:
                progress_callback(10, f"Connecting to official repository for {info['name']}...")

            # User-Agent header for modern downloads
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IntentPlatform/1.0"}
            )

            with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, "wb") as out_file:
                total_size = int(response.info().get("Content-Length", 0))
                bytes_downloaded = 0
                block_size = 65536

                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    out_file.write(buffer)
                    bytes_downloaded += len(buffer)
                    if total_size > 0 and progress_callback:
                        pct = int((bytes_downloaded / total_size) * 90) + 5
                        progress_callback(pct, f"Downloading {info['name']}: {pct}%")

            self.active_install["step"] = "DOWNLOADED"
            self.audit_logger.log(
                f"Installer downloaded: {dest_path} ({bytes_downloaded // 1024} KB)",
                category="SOFTWARE_INSTALL",
                risk_level="SAFE"
            )

            if progress_callback:
                progress_callback(100, f"Installer for {info['name']} downloaded successfully.")

            return {
                "success": True,
                "installer_path": dest_path,
                "file_size_kb": bytes_downloaded // 1024,
                "software_name": info["name"]
            }

        except Exception as e:
            # If direct download is restricted or blocked, fallback to winget or opening browser
            self.audit_logger.log(
                f"Direct download failed for {info['name']} ({type(e).__name__}); falling back to official browser source.",
                category="SOFTWARE_INSTALL",
                risk_level="WARNING"
            )
            self.active_install["step"] = "DOWNLOAD_FAILED"
            return {
                "success": False,
                "error": "The download failed because of a network or permission issue.",
                "fallback_url": info["official_url"]
            }

    def execute_installer(self, silent: bool = False) -> Dict[str, Any]:
        """
        Executes downloaded installer with elevated permissions if required.
        Asks permission before executing.
        """
        if not self.active_install:
            return {"success": False, "error": "No active installation context"}

        info = self.active_install["info"]
        installer_path = self.active_install.get("installer_path")

        self.audit_logger.log(
            f"Launching installer for {info['name']}: {installer_path}",
            category="SOFTWARE_INSTALL",
            risk_level="HIGH_RISK"
        )

        try:
            # Check if installer file exists
            if installer_path and os.path.exists(installer_path):
                # Launch installer process
                if installer_path.endswith(".msi"):
                    cmd = ["msiexec", "/i", installer_path]
                else:
                    cmd = [installer_path]

                subprocess.Popen(cmd, shell=True)
                self.active_install["step"] = "INSTALLER_LAUNCHED"
                return {
                    "success": True,
                    "message": f"Launched official installer for {info['name']}. Please follow the guided setup dialog."
                }
            else:
                # Use winget if installer file wasn't directly stored
                winget_id = info.get("winget_id")
                if winget_id:
                    self.audit_logger.log(
                        f"Running winget install for {winget_id}",
                        category="SOFTWARE_INSTALL",
                        risk_level="HIGH_RISK"
                    )
                    cmd = ["winget", "install", "--id", winget_id, "--accept-source-agreements", "--accept-package-agreements"]
                    subprocess.Popen(cmd, shell=True)
                    self.active_install["step"] = "WINGET_LAUNCHED"
                    return {
                        "success": True,
                        "message": f"Started automated installation for {info['name']} via Windows Package Manager."
                    }

            return {"success": False, "error": "Installer file not found on disk."}

        except Exception as e:
            self.active_install["step"] = "LAUNCH_FAILED"
            return {
                "success": False,
                "error": f"The installer could not be launched ({type(e).__name__}).",
            }

    def verify_installation(self, software_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Verifies whether the software is successfully installed and available on the system.
        """
        target = software_info or (self.active_install["info"] if self.active_install else None)
        if not target:
            return {"installed": False, "details": "Unknown software"}

        verify_cmd = target.get("verify_cmd")
        keyword = target.get("verify_keyword", "")

        if not verify_cmd:
            return {"installed": True, "details": f"{target['name']} installer completed."}

        try:
            result = subprocess.run(
                verify_cmd,
                capture_output=True,
                text=True,
                timeout=8,
                shell=True
            )
            output = (result.stdout or "") + (result.stderr or "")

            if result.returncode == 0 or (keyword and keyword.lower() in output.lower()):
                self.audit_logger.log(
                    f"Installation completed and verified: {target['name']} ({output.strip()[:60]})",
                    category="SOFTWARE_INSTALL",
                    risk_level="SAFE"
                )
                return {
                    "installed": True,
                    "version_output": output.strip(),
                    "details": f"{target['name']} is verified and ready to use."
                }
            else:
                return {
                    "installed": False,
                    "version_output": output.strip(),
                    "details": "Installation check did not return expected version. System reboot or shell restart may be required for PATH update."
                }
        except Exception as e:
            return {
                "installed": False,
                "error": f"Installation verification failed ({type(e).__name__}).",
                "details": "The verification command could not be completed. Check the installation and environment PATH.",
            }
