"""config.py — v6 Gemini-only config"""
import os
from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY","")
EMAIL_ADDRESS  = os.getenv("EMAIL_ADDRESS","")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD","")
PASS_THRESHOLD = float(os.getenv("PASS_THRESHOLD","60.0"))
APP_BASE_URL   = os.getenv("APP_BASE_URL","http://localhost:8501")

def validate_config():
    errors = []
    if not GEMINI_API_KEY or GEMINI_API_KEY == "paste-your-gemini-key-here":
        errors.append("GEMINI_API_KEY not set. Get free key at https://aistudio.google.com/app/apikey")
    return errors
