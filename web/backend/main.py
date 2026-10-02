"""FastAPI application for the browser-accessible Intent OS experience."""

import logging
import sys
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web.backend.auth import (
    SESSION_COOKIE,
    _read_session,
    login,
    logout,
    public_demo_enabled,
    require_user,
    web_login_configured,
)
from web.backend.cloud_agent import CloudAgentError, cloud_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("intent_os.web")

app = FastAPI(title="Intent OS Web API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)


class AgentRequest(BaseModel):
    action: Literal["status", "activate", "deactivate"] = "status"


@app.get("/api/status")
def get_status(request: Request):
    public_demo = public_demo_enabled()
    authenticated = public_demo or bool(_read_session(request.cookies.get(SESSION_COOKIE, "")))
    login_ready = web_login_configured()
    ai_ready = cloud_agent.configured
    return {
        "application": "Intent OS",
        "status": "available" if (public_demo or login_ready) and ai_ready else "degraded",
        "authenticated": authenticated,
        "public_demo": public_demo,
        "web_login_configured": login_ready,
        "gemini_configured": ai_ready,
        "capabilities": ["text chat", "AI reasoning", "web dashboard", "session status"],
        "desktop_only": [
            "screen understanding", "camera and gesture control", "microphone voice control",
            "mouse and keyboard automation", "local application control",
        ],
    }


@app.post("/api/login")
def post_login(payload: LoginRequest, response: Response):
    username = login(payload.username, payload.password, response)
    return {"authenticated": True, "username": username, "message": "Signed in to Intent OS Web."}


@app.post("/api/logout")
def post_logout(response: Response, _username: str = Depends(require_user)):
    logout(response)
    return {"authenticated": public_demo_enabled()}


@app.post("/api/chat")
def post_chat(payload: ChatRequest, username: str = Depends(require_user)):
    if not cloud_agent.configured:
        raise HTTPException(
            status_code=503,
            detail={"code": "gemini_not_configured", "message": "AI chat is unavailable until GEMINI_API_KEY is configured."},
        )
    history = [{"role": item.role, "content": item.content} for item in payload.history]
    try:
        answer = cloud_agent.reply(payload.message, history)
    except CloudAgentError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "ai_unavailable", "message": str(error)},
        ) from None
    logger.info("Web chat completed for authenticated user")
    return {"reply": answer, "capability": "text_chat", "desktop_action_taken": False}


@app.post("/api/agent")
def post_agent(payload: AgentRequest, username: str = Depends(require_user)):
    return {
        "agent": "Intent OS Web Agent",
        "status": "ready",
        "requested_action": payload.action,
        "message": "The text-only web agent is ready. Device control remains available in the Desktop Agent.",
        "desktop_action_taken": False,
    }