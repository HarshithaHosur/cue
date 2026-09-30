# AI Interview Agent Module Documentation

## Overview
The AI Interview Agent is an intelligent assistant integrated into the **Intent AI Platform**. It acts as a co-pilot for human interviewers before, during, and after technical/behavioural interviews.

The agent **does not replace the interviewer** or make hiring decisions. It monitors integrity signals, tracks pace and clarity, accepts voice and gesture commands, and compiles post-interview reports with neutral, objective analytics.

---

## Architecture & Subsystems

### 1. Database Store (`core/interview/store.py`)
- Standardized SQLite database integration (`database/local_store.db`).
- Tracks interviews, timeline events, transcripts, questions, notes, and generated reports.

### 2. State Machine (`core/interview/session.py`)
- Strictly enforced lifecycle states: `SETUP` -> `VERIFYING` -> `LIVE` -> `ENDED` -> `REPORTED`.
- Prevents illegal state transitions (e.g. `VERIFYING` directly to `ENDED`).

### 3. Integrity & Observation Engine (`core/interview/observation_engine.py`)
- Integrates with MediaPipe face mesh and system focus events.
- Signals captured:
  - Multi-face presence (`multi_face`)
  - Off-screen gaze duration (`gaze_away`)
  - No face in frame (`no_face`)
  - Application window switching (`app_switched`)
  - Tab switching (`tab_switched`)
  - Clipboard operations (`paste_detected`)
- Uses neutral, non-accusatory language for event logs (e.g., `"Multiple faces detected in camera frame"`).

### 4. Voice Analytics & Routing (`core/interview/voice_router.py` & `core/interview/voice_analyzer.py`)
- **Voice Routing**: Parses 13 specialized voice commands during interviews:
  - `"next question"`, `"previous question"`, `"flag moment"`, `"pause interview"`, `"resume interview"`, `"end interview"`, `"generate summary"`, `"repeat question"`, `"explain answer"`, `"add note <text>"`, `"mark candidate ready"`, `"start recording"`, `"stop recording"`.
- **Voice Analytics**: Calculates WPM (words per minute), speech clarity metrics, and filler word frequency (`"um"`, `"uh"`, `"like"`, `"you know"`).

### 5. Gesture Routing (`core/interview/gesture_router.py`)
- Maps real-time hand gestures to interview controls:
  - `swipe_right` -> Next Question
  - `swipe_left` -> Previous Question
  - `fist` -> Pass through for system screenshots

### 6. Gemini AI Assistant (`core/interview/ai_assistant.py`)
- Powered by Google Gemini API (`gemini-1.5-flash`).
- Provides real-time suggested follow-up questions, technical evaluation hints, and instant question summaries.

### 7. Post-Interview Report Generator (`core/interview/report_generator.py`)
- Compiles candidate metadata, timeline observations, voice analytics, notes, and key insights.
- Evaluates candidate on Technical Competency, Communication & Clarity, Problem Solving, and Culture Fit.
- Generates neutral summaries with mandatory disclaimer: *"Final decision rests with the interviewer."*
- Features local template fallback if API connectivity is unavailable.

---

## Configuration & Privacy

### Environment Variables
Set the following in your `.env` file or environment:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Privacy & Ethics Guardrails
- **Neutral Phrasing**: No biased or aggressive labels like "cheating", "fraud", or "dishonest".
- **Interviewer Control**: AI serves purely as an observer and recorder; hiring decisions remain 100% human-driven.
- **Data Locality**: Session logs, notes, and local events are stored in the local SQLite database (`local_store.db`).

---

## Verification & Testing
Run the acceptance test suites to confirm complete end-to-end operational readiness:

```powershell
# Run AI Interview Agent Acceptance Test Suite (52 tests)
venv\Scripts\python.exe scratch_test_interview.py

# Run Core HCI Backend Verification Suite
venv\Scripts\python.exe scratch_test_backend.py
```

---

## Known Limitations
1. Speech recognition accuracy depends on audio input quality and background noise level.
2. OpenCV/MediaPipe frame processing operates at standard webcam framerates (15-30 FPS).
