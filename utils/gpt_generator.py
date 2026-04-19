"""
utils/gpt_generator.py
Backward-compatible wrapper — all calls now go through Gemini (free).
"""
from utils.gemini_ai import (
    generate_mcqs_from_topic,
    generate_mcqs_from_text,
    chatbot_answer as generate_chatbot_answer,
    extract_topics_locally,
    is_configured,
    get_gemini_key,
)

__all__ = [
    "generate_mcqs_from_topic",
    "generate_mcqs_from_text",
    "generate_chatbot_answer",
    "extract_topics_locally",
    "is_configured",
    "get_gemini_key",
]
