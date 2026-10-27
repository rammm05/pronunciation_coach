# Pronunciation Coach (FastAPI + Groq)

Frontend: `static/index.html` · Backend: `main.py` · Only needs a **Groq API key**.

## Run

```bash
# 1. (optional) virtual environment
python -m venv .venv
python3 -m venv .venv           # Mac

.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac / Linux

# 2. install
pip install -r requirements.txt

# 3. add your key
copy .env.example .env          # Windows   (Mac/Linux: cp .env.example .env)
# open .env and paste your GROQ_API_KEY

# 4. start
uvicorn main:app --reload
```

Open **http://localhost:8000** in Chrome (the mic only works on localhost or https).

## How it works

| Frontend call            | Backend           | Groq model                |
|--------------------------|-------------------|---------------------------|
| `/api/transcribe`        | audio -> text     | `whisper-large-v3-turbo`  |
| `/api/coach` (analyze)   | grammar score     | `llama-3.3-70b-versatile` |
| `/api/coach` (talk)      | chat reply + tip  | `llama-3.3-70b-versatile` |

Voice playback uses the browser's built-in speech, so no extra keys are needed.
If the backend is down, the frontend falls back to its offline mode automatically.

## Check it's working

Visit http://localhost:8000/api/health — you should see `{"ok": true, ...}`.

## Deploy (Render / Railway)

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Add `GROQ_API_KEY` as an environment variable (don't upload `.env`).
