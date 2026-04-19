"""
utils/gemini_ai.py — FINAL FIX
================================
Correct model list matching what Gemini API supports in 2025/2026.
Handles quota errors with automatic retry after short wait.

Your key supports:
  gemini-2.5-flash-lite  ← fastest, try first
  gemini-2.5-flash       ← best quality
  gemini-2.5-pro         ← most powerful
  gemini-2.0-flash       ← reliable fallback
  gemini-2.0-flash-lite  ← lite fallback
"""

import json, os, re, time, urllib.request, urllib.error
from dotenv import load_dotenv
load_dotenv()

# ── Correct model list (ordered: fastest → most powerful) ───────────────────
GEMINI_MODELS = [
    "gemini-2.5-flash-lite",   # fastest, lowest quota — try first
    "gemini-2.5-flash",        # fast + high quality
    "gemini-2.0-flash",        # reliable fallback
    "gemini-2.0-flash-lite",   # lite fallback
    "gemini-2.0-flash-001",    # versioned fallback
    "gemini-2.5-pro",          # most powerful (may be slower)
]

# Gemini API base URL — v1beta works for all models above
BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)


# ── Key helpers ──────────────────────────────────────────────────────────────

def get_gemini_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()

def is_configured() -> bool:
    k = get_gemini_key()
    return bool(k) and k not in ("", "paste-your-gemini-key-here")


# ── Core API call ────────────────────────────────────────────────────────────

def _call_gemini(prompt: str, max_tokens: int = 1500) -> str:
    """
    Calls Gemini API. Tries each model in GEMINI_MODELS.
    On quota error (429): waits 5 seconds and tries the next model.
    Returns text response from first model that succeeds.
    """
    key = get_gemini_key()
    if not key or key == "paste-your-gemini-key-here":
        raise ValueError(
            "Gemini API key not set.\n"
            "1. Go to https://aistudio.google.com/app/apikey\n"
            "2. Click 'Create API Key' (free, no credit card)\n"
            "3. Open your .env file and set:\n"
            "   GEMINI_API_KEY=AIzaSy...\n"
            "4. Save and restart the app"
        )

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
            "topP": 0.9,
        }
    }).encode("utf-8")

    last_error = ""
    tried      = []

    for model in GEMINI_MODELS:
        url = BASE_URL.format(model=model, key=key)
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = (
                result
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            if text:
                return text          # ← success
            else:
                last_error = f"{model}: empty response"
                tried.append(model)
                continue

        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                err_msg = json.loads(raw).get("error", {}).get("message", raw)
            except Exception:
                err_msg = raw[:200]

            tried.append(model)

            # Quota exceeded → wait 5s and try next model
            if e.code == 429 or "quota" in err_msg.lower() or "RESOURCE_EXHAUSTED" in err_msg:
                last_error = f"{model}: quota exceeded (429)"
                time.sleep(5)   # wait before trying next model
                continue

            # Model not found / not supported → try next immediately
            if any(p in err_msg for p in [
                "not found", "not supported", "INVALID_ARGUMENT",
                "does not exist", "deprecated", "not available"
            ]):
                last_error = f"{model}: not available"
                continue

            # Bad API key → stop immediately, no point trying more models
            if any(p in err_msg for p in [
                "API_KEY_INVALID", "API key not valid", "PERMISSION_DENIED"
            ]):
                raise ValueError(
                    "Your Gemini API key is invalid.\n"
                    "Get a new key at: https://aistudio.google.com/app/apikey"
                )

            # Other HTTP error → try next
            last_error = f"{model}: HTTP {e.code} — {err_msg[:100]}"
            continue

        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Network error. Check your internet connection.\n{e.reason}"
            )
        except Exception as e:
            last_error = f"{model}: {str(e)[:80]}"
            tried.append(model)
            continue

    # All models failed
    raise RuntimeError(
        f"All Gemini models failed.\n\n"
        f"Models tried: {', '.join(tried)}\n"
        f"Last error: {last_error}\n\n"
        f"Most likely cause: FREE tier quota exhausted for today.\n"
        f"Solutions:\n"
        f"  1. Wait a few minutes and try again (quota resets per minute)\n"
        f"  2. Generate a new API key: https://aistudio.google.com/app/apikey\n"
        f"  3. Add billing to your Google account for higher quota"
    )


# ── JSON parser ──────────────────────────────────────────────────────────────

def _parse_questions(raw: str, difficulty: str) -> list:
    """Parses Gemini JSON response into question dicts."""
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except Exception:
                raise ValueError("Could not parse AI response. Try again.")
        else:
            raise ValueError(f"Unexpected AI response format. Try again.\nGot: {raw[:150]}")

    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                data = v
                break

    if not isinstance(data, list):
        raise ValueError("AI response was not a list of questions.")

    return [_validate(q, difficulty) for q in data if isinstance(q, dict)]


def _validate(q: dict, fallback: str) -> dict:
    for k in ["question","option_a","option_b","option_c",
               "option_d","correct_option","difficulty","explanation"]:
        if k not in q:
            q[k] = "" if k != "correct_option" else "A"
    c = str(q["correct_option"]).strip().upper()
    q["correct_option"] = c if c in ["A","B","C","D"] else "A"
    if q.get("difficulty") not in ["easy","moderate","hard"]:
        q["difficulty"] = fallback
    q["question"] = str(q.get("question","")).strip()
    return q


# ── Local topic extractor (no API — instant) ─────────────────────────────────

def extract_topics_locally(text: str, max_topics: int = 8) -> list:
    """
    Extracts key topic sentences from document using pure Python.
    No API call — runs instantly. Prevents timeout from large PDFs.
    """
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if 25 < len(s.strip()) < 300]

    if not sentences:
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
        return lines[:max_topics]

    edu_kw = [
        'define','definition','concept','principle','theory','method',
        'process','algorithm','function','structure','type','example',
        'important','key','main','primary','objective','unit','chapter',
        'topic','describe','explain','understand','fundamental','basic',
        'is defined','refers to','used to','consists of','known as',
    ]
    scored = []
    for i, s in enumerate(sentences):
        score  = sum(2 for kw in edu_kw if kw in s.lower())
        score += max(0, 10 - i)
        wc     = len(s.split())
        score += 3 if 8 <= wc <= 25 else (1 if wc > 25 else 0)
        scored.append((score, s))

    scored.sort(reverse=True)
    return [s[1] for s in scored[:max_topics]]


# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM = (
    "You are an expert MCQ generator for educational assessments. "
    "Output ONLY a valid JSON array of question objects. "
    "No markdown, no code fences, no extra text. "
    "Each object must have exactly: "
    "question, option_a, option_b, option_c, option_d, "
    "correct_option (A/B/C/D), difficulty, explanation."
)

def _build_prompt(topics: list, n: int, difficulty: str) -> str:
    t_str = "\n".join(f"• {t[:120]}" for t in topics[:7])
    guide = {"easy":"basic recall","moderate":"comprehension and application",
             "hard":"analysis and evaluation"}.get(difficulty,"comprehension")
    return (
        f"{_SYSTEM}\n\n"
        f"Generate exactly {n} {difficulty}-level MCQ questions ({guide}).\n"
        f"Topics:\n{t_str}\n\n"
        f'Return JSON array: [{{"question":"...","option_a":"...","option_b":"...",'
        f'"option_c":"...","option_d":"...","correct_option":"A",'
        f'"difficulty":"{difficulty}","explanation":"..."}}]'
    )


# ── Batch generator ──────────────────────────────────────────────────────────

def _generate_batch(topics: list, n: int, difficulty: str) -> list:
    raw = _call_gemini(_build_prompt(topics, n, difficulty), max_tokens=1500)
    return _parse_questions(raw, difficulty)


# ── Public: generate from topic ──────────────────────────────────────────────

def generate_mcqs_from_topic(topic: str, subject: str,
                              num_questions: int = 5,
                              difficulty: str = "moderate") -> list:
    topics    = [f"{topic} ({subject})", topic, subject,
                 f"Key concepts in {topic}", f"{topic} fundamentals"]
    all_qs    = []
    remaining = num_questions

    while remaining > 0:
        n = min(5, remaining)
        try:
            batch = _generate_batch(topics, n, difficulty)
            all_qs.extend(batch)
            remaining -= len(batch)
            if not batch:
                break
        except Exception as e:
            if all_qs:
                break
            raise RuntimeError(str(e))

    return all_qs[:num_questions]


# ── Public: generate from document ──────────────────────────────────────────

def generate_mcqs_from_text(text: str, num_questions: int = 5,
                             difficulty: str = "moderate") -> list:
    """
    Fast: extracts topics locally first, then sends short prompt to Gemini.
    No timeout. Works even for large PDFs.
    """
    topics = extract_topics_locally(text, max_topics=8)
    if not topics:
        topics = [text[:400]]

    all_qs    = []
    remaining = num_questions

    while remaining > 0:
        n = min(5, remaining)
        try:
            batch = _generate_batch(topics, n, difficulty)
            all_qs.extend(batch)
            remaining -= len(batch)
            if not batch:
                break
        except Exception as e:
            if all_qs:
                break
            raise RuntimeError(str(e))

    return all_qs[:num_questions]


# ── Public: chatbot ──────────────────────────────────────────────────────────

def chatbot_answer(question: str, context: str = "") -> str:
    prompt = (
        "You are a friendly AI tutor. Answer in under 150 words. "
        "Be clear, encouraging, and give an example if helpful.\n\n"
        + (f"Topic: {context}\n\n" if context else "")
        + f"Student question: {question}"
    )
    try:
        return _call_gemini(prompt, max_tokens=300)
    except Exception as e:
        return f"⚠️ AI unavailable: {e}"
