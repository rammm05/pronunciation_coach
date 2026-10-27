"""
Pronunciation Coach backend (FastAPI + Groq).

Endpoints used by the frontend:
  POST /api/transcribe  multipart(audio, lang)        -> {"text": "..."}
  POST /api/coach       JSON {mode, text, history?}   -> {"reply","tip"} or {"grammar","tips"}

The Groq API key stays on the server (in .env) and never reaches the browser.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from pydantic import BaseModel

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

API_KEY = os.getenv("GROQ_API_KEY", "").strip()
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")
CHAT_MODEL = os.getenv("CHAT_MODEL", "llama-3.3-70b-versatile")

if not API_KEY or API_KEY.startswith("your_"):
    raise SystemExit("Missing GROQ_API_KEY. Copy .env.example to .env and paste your key.")

client = Groq(api_key=API_KEY)
app = FastAPI(title="Pronunciation Coach")

# Lets you also open static/index.html straight from disk during development.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- transcribe
@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...), lang: str = Form("en-IN")):
    data = await audio.read()
    if len(data) < 800:  # empty / too-short recording
        return {"text": ""}
    try:
        r = client.audio.transcriptions.create(
            file=(audio.filename or "speech.webm", data, audio.content_type or "audio/webm"),
            model=WHISPER_MODEL,
            language=(lang or "en").split("-")[0],
            temperature=0,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq transcription failed: {e}")
    return {"text": (r.text or "").strip()}


# --------------------------------------------------------------------- coach
class CoachIn(BaseModel):
    mode: str                      # "analyze" | "talk"
    text: str
    history: list[dict] | None = None   # frontend items: {r: "u"|"c", t: str, mr?: str}


ANALYZE_SYSTEM = (
    "You are an English speaking coach. Judge the GRAMMAR of the learner's spoken text "
    "(it is a speech transcript, so ignore punctuation and capitalisation). "
    'Reply ONLY with JSON: {"grammar": <integer 0-100>, "tips": ["<short tip>", "<short tip>"]}. '
    "Give at most 3 short, specific, encouraging tips."
)

TALK_SYSTEM = (
    "You are a friendly English conversation partner and pronunciation coach for an Indian learner. "
    "Reply naturally in 1-3 short sentences and end with a simple follow-up question to keep them talking. "
    "If the learner made a grammar or word-choice mistake, give ONE short correction as the tip "
    "(e.g. 'Say \"I went\" instead of \"I goed\"'); if there was no mistake, give a short encouraging tip. "
    'Reply ONLY with JSON: {"reply": "<your reply>", "tip": "<one short tip>"}.'
)


def history_to_messages(history, current_text):
    """Convert frontend chat history into Groq chat messages."""
    msgs = []
    for m in (history or [])[-8:]:
        content = str(m.get("t", "")).strip()
        if not content:
            continue
        msgs.append({"role": "user" if m.get("r") == "u" else "assistant", "content": content})
    # The frontend already appended the current message to history; avoid duplicating it.
    if msgs and msgs[-1]["role"] == "user" and msgs[-1]["content"] == current_text:
        msgs.pop()
    return msgs


def ask_json(messages):
    try:
        r = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.6,
            max_tokens=400,
        )
        return json.loads(r.choices[0].message.content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Model returned invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Groq chat failed: {e}")


@app.post("/api/coach")
async def coach(p: CoachIn):
    text = p.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    if p.mode == "analyze":
        out = ask_json([
            {"role": "system", "content": ANALYZE_SYSTEM},
            {"role": "user", "content": text[:6000]},
        ])
        try:
            grammar = max(0, min(100, int(round(float(out.get("grammar", 0))))))
        except (TypeError, ValueError):
            grammar = 0
        tips = [str(t) for t in (out.get("tips") or [])][:3]
        return {"grammar": grammar, "tips": tips}

    if p.mode == "talk":
        msgs = [{"role": "system", "content": TALK_SYSTEM}]
        msgs += history_to_messages(p.history, text)
        msgs.append({"role": "user", "content": text[:2000]})
        out = ask_json(msgs)
        return {"reply": str(out.get("reply", "")).strip(), "tip": str(out.get("tip", "")).strip()}

    raise HTTPException(status_code=400, detail="mode must be 'analyze' or 'talk'")


@app.get("/api/health")
async def health():
    return {"ok": True, "whisper": WHISPER_MODEL, "chat": CHAT_MODEL}


# ------------------------------------------------------------------ frontend
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(BASE / "static" / "index.html")
