# Browser Web Workspace

The existing PySide6 application remains the full local multimodal desktop agent. The additive browser version lives in `web/frontend` and `web/backend`: React/Vite serves the sign-in and workspace UI, and FastAPI provides session login, status, and text-only Gemini chat. The cloud API does not import the desktop IntentEngine, PySide6 UI, local database, screen capture, OCR, camera, microphone, `pyautogui`, or Windows APIs.

The web login is a configurable demo account, not the desktop biometric/user database. Set `WEB_DEMO_USERNAME`, `WEB_DEMO_PASSWORD`, and a random `WEB_SESSION_SECRET` of at least 32 characters. Do not reuse a personal password. For a public judge demo, set `WEB_PUBLIC_DEMO=true`; the dashboard opens without sign-in, and the API permits anonymous web-agent requests. This is an intentionally public, shared demo, not private authentication. When the flag is false or absent, the signed-session login remains required. The web agent supports text conversation only; camera, gestures, microphone, screen understanding, and mouse/keyboard automation remain available only in the local desktop application. The web agent must not be treated as controlling the judge's computer.

## Local Web Development

From the repository root (`intent_platform`):

1. Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY`, `WEB_DEMO_USERNAME`, `WEB_DEMO_PASSWORD`, and `WEB_SESSION_SECRET`. `.env` is ignored by Git.
2. Install the web API dependencies with `python -m pip install -r requirements.txt`.
3. Start the API in one terminal:

      ```powershell
      uvicorn web.backend.main:app --reload
      ```

4. Start the frontend in another terminal:

      ```powershell
      cd web/frontend
      npm install
      npm run dev
      ```

5. Open the Vite URL (normally `http://localhost:5173`). The dev server proxies `/api` to `http://127.0.0.1:8000`.

The desktop application remains launched separately with `python main.py` from the repository root, or from the parent workspace using `python run_intent_platform.py`.

## Vercel Deployment

1. Import the `intent_platform` Git repository into Vercel and keep the project root at the repository root. `vercel.json` builds `web/frontend` and routes `/api/*` to the Python FastAPI function at `api/index.py`.
2. In Vercel Project Settings -> Environment Variables, set `WEB_PUBLIC_DEMO` to `true` for anonymous judge access and set `GEMINI_API_KEY` server-side. Optionally set `GEMINI_MODEL` (the existing default is used otherwise). If public demo mode is disabled, set `WEB_DEMO_USERNAME`, `WEB_DEMO_PASSWORD`, and a cryptographically random `WEB_SESSION_SECRET` instead. Do not put real values into Git or source files.
3. Enable the Production environment variables, deploy, and use the generated URL such as `https://intent-os-demo.vercel.app` as the single judge-facing entry point. The root route opens at sign-in; after login, users reach the dashboard and text-only agent.
4. Check `https://<deployment-domain>/api/status` for web API, login configuration, and Gemini configuration state. It reports booleans only and never returns the key.

Vercel does not host the PySide6 desktop app and cannot control a judge's local device. Gemini chat needs a valid server-side `GEMINI_API_KEY`; without it the API returns a safe setup message. Demo-account login is intentionally simple and is not a replacement for production identity management, persistent user accounts, rate limiting, or a full auth provider.

## Web API

- `GET /api/status`: public health/configuration and capability status.
- `POST /api/login`: validates configured demo credentials and sets a signed HttpOnly session cookie.
- `POST /api/logout`: expires the authenticated session.
- `POST /api/chat`: authenticated text-only Gemini conversation; never executes desktop actions.
- `POST /api/agent`: authenticated web-agent status response; it explicitly does not activate the local desktop agent.

# CUE – Contextual Unified Experience

## Multimodal AI Desktop Companion

CUE (Contextual Unified Experience) is a multimodal AI desktop companion that combines **Voice Recognition, Gesture Recognition, Screen Understanding, Context Awareness, AI Reasoning, and Safe Desktop Automation** to create a natural human-computer interaction experience.

Unlike traditional chatbots, CUE understands **what the user says, what the user sees on the screen, and what the user is trying to accomplish**, allowing it to assist users intelligently across multiple applications.

---

# Features

### Authentication
- Secure Login & Signup
- Face Authentication
- Continuous Face Verification
- Unauthorized User Detection

### Voice Interaction
- Wake Word Activation ("System")
- Natural Language Commands
- Voice Responses
- Context-Aware Conversations

### Gesture Recognition
- Virtual Cursor Control
- Click & Drag using Pinch
- Smart Scrolling
- Zoom In / Zoom Out
- Volume Control
- Tab Navigation
- Screenshot Capture

### Screen Understanding
- Understands the active screen
- Detects applications and websites
- Reads terminal errors
- Understands UI elements
- Context-aware assistance

### AI Customer Support
- Amazon Customer Support
- Meesho Customer Support
- Order Tracking
- Returns & Replacement Guidance
- Refund Assistance
- Customer Support Navigation
- Screen-guided assistance

### AI Technical Support
- Software Installation Assistant
- Terminal Error Explanation
- Git Error Debugging
- Python, Java & Node.js Error Assistance
- Wi-Fi Troubleshooting
- Battery Health Monitoring
- Windows Settings Assistance

### AI Interview Coach
- Resume Analysis
- Live Interview Assistance
- AI Follow-up Questions
- Rubric Tracking
- Live Transcript
- Code Explanation
- Interview Summary Report

---

# Supported Gestures

| Gesture | Action |
|----------|--------|
| 👍 Thumbs Up | Volume Up / Zoom In |
| 👎 Thumbs Down | Volume Down / Zoom Out |
| ☝️ Index Finger | Virtual Cursor |
| ✌️ One Peace Sign | Disable Cursor |
| 🤏 Pinch | Left Click |
| 🤏 Hold Pinch | Drag & Drop |
| 👐 Two Open Hands | Enable Scroll |
| ✌️✌️ Two Peace Signs | Stop Scroll |
| 🖐️ Left → Right | Next Tab |
| 🖐️ Right → Left | Previous Tab |
| ✊ Fist | Take Screenshot |

---

# Technology Stack

- Python
- PySide6
- Gemini 2.5 Flash
- Gemini Vision
- OpenCV
- MediaPipe
- EasyOCR
- MSS
- PyAutoGUI
- Pynput
- psutil
- pywin32

---

# System Workflow

```
Login
      ↓
Face Authentication
      ↓
Dashboard
      ↓
Choose Module
      ↓
Activate AI Agent
      ↓
Voice + Gestures + Screen Understanding
      ↓
AI Reasoning
      ↓
Safe Automation
      ↓
Task Completed
```

---

# Project Modules

### 1. AI Customer Support
Helps users navigate Amazon and Meesho customer support, guides them through returns, replacements, refunds, and order-related issues using voice, gestures, and screen understanding.

### 2. AI Technical Support
Assists users with software installation, debugging terminal errors, solving Wi-Fi issues, checking battery health, and understanding system settings.

### 3. AI Interview Coach
Provides interview assistance by analyzing resumes, tracking interview rubrics, suggesting follow-up questions, explaining code, and generating interview summaries.

---

# What Makes CUE Different?

Unlike traditional AI assistants, CUE combines:

- 🎤 Voice Recognition
- ✋ Gesture Recognition
- 👀 Screen Understanding
- 🧠 Context Awareness
- 🤖 AI Reasoning
- 🔒 Continuous Authentication
- ⚡ Safe Desktop Automation

This enables users to interact with their computer naturally without relying entirely on the keyboard and mouse.

---

# Future Scope

- Cross-platform support
- Browser extension
- Enterprise deployment
- Multi-language support
- Additional e-commerce platforms
- Enhanced AI automation

---

# Team

**Project:** CUE – Contextual Unified Experience

Hackathon Project

---

# License

This project is developed for educational and hackathon purposes.
