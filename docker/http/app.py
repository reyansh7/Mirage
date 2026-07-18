from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

API_URL = os.getenv("LOG_API_URL", "http://172.28.0.10:8000").rstrip("/")

app = FastAPI(title="Acme Employee Portal")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

VALID_USERS = {
    "admin": "admin123",
    "developer": "Welcome1!",
    "alice": "Welcome1!",
}


async def ensure_session(request: Request) -> str | None:
    """One logging session per browser cookie (not a global process session)."""
    existing = request.cookies.get("hp_session")
    if existing:
        return existing
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(
                f"{API_URL}/session",
                json={
                    "source_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                    "service": "http",
                    "meta": {"portal": "acme"},
                },
            )
            if resp.is_success:
                return resp.json().get("id")
    except Exception:
        pass
    return None


async def log_event(
    request: Request,
    event_type: str,
    payload: dict | None = None,
    session_id: str | None = None,
) -> str | None:
    sid = session_id or await ensure_session(request)
    body = {
        "service": "http",
        "event_type": event_type,
        "ip": request.client.host if request.client else None,
        "session": sid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {},
    }
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(f"{API_URL}/events", json=body)
    except Exception:
        pass
    return sid


def _request_payload(request: Request, status: int | None = None) -> dict:
    return {
        "method": request.method,
        "url": str(request.url.path),
        "path": str(request.url.path),
        "query": str(request.url.query) if request.url.query else None,
        "headers": {
            k: v
            for k, v in request.headers.items()
            if k.lower() in ("user-agent", "referer", "accept", "content-type", "cookie", "origin")
        },
        "cookies": dict(request.cookies),
        "user_agent": request.headers.get("user-agent"),
        "response_code": status,
        "status": status,
    }


@app.middleware("http")
async def access_log(request: Request, call_next):
    response = await call_next(request)
    # Attach session cookie if created during request
    sid = getattr(request.state, "hp_session", None) or request.cookies.get("hp_session")
    if not sid:
        sid = await ensure_session(request)
        if sid:
            response.set_cookie("hp_session", sid, httponly=True)

    await log_event(
        request,
        "HTTP_REQUEST",
        _request_payload(request, response.status_code),
        session_id=sid,
    )
    return response


def _authed(request: Request) -> bool:
    return bool(request.cookies.get("session"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "home.html",
        {"request": request, "title": "Acme Employee Portal"},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    ok = VALID_USERS.get(username) == password
    sid = await ensure_session(request)
    event_type = "AUTH_SUCCESS" if ok else "AUTH_FAILURE"
    await log_event(
        request,
        event_type,
        {
            "username": username,
            "user": username,
            "success": ok,
            "method": "form",
        },
        session_id=sid,
    )
    if ok:
        await log_event(
            request,
            "LOGIN",
            {"username": username, "user": username},
            session_id=sid,
        )
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie("session", str(uuid.uuid4()), httponly=True)
        resp.set_cookie("portal_user", username, httponly=False)
        if sid:
            resp.set_cookie("hp_session", sid, httponly=True)
        return resp
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid credentials"},
        status_code=401,
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": request.cookies.get("portal_user", "employee")},
    )


@app.get("/announcements", response_class=HTMLResponse)
async def announcements(request: Request):
    if not _authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("announcements.html", {"request": request})


@app.get("/helpdesk", response_class=HTMLResponse)
async def helpdesk(request: Request):
    if not _authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("helpdesk.html", {"request": request})


@app.get("/hr", response_class=HTMLResponse)
async def hr(request: Request):
    if not _authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("hr.html", {"request": request})


@app.get("/finance", response_class=HTMLResponse)
async def finance(request: Request):
    if not _authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("finance.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    if not _authed(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("admin.html", {"request": request})
