"""
OpenAI LLM integration layer.

Used ONLY for:
  1. Answering follow-up questions about a specific scheme (with context)
  2. Language detection (Hindi / English)

NOT used for flow control — that's the state machine's job.
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    """Lazy-init the OpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def ask_llm_fallback(
    user_message: str,
    scheme_context: dict,
    user_profile: dict,
    language: str = "en",
) -> str:
    """
    Ask the LLM a question about a specific scheme.

    The LLM receives full scheme data as context so it never needs to hallucinate.
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured — using fallback response")
        return (
            "I'd love to help with more details, but my AI assistant "
            "is not configured yet. Please check the scheme details above "
            "or visit the official website."
        )

    try:
        client = _get_client()
        user_prompt = build_user_prompt(
            user_message=user_message,
            scheme_context=scheme_context,
            user_profile=user_profile,
            language=language,
        )

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.3,  # Low temp for factual, grounded responses
        )

        answer = response.choices[0].message.content.strip()
        logger.info("LLM response generated (%d chars)", len(answer))
        return answer

    except Exception as e:
        logger.error("OpenAI API error: %s", str(e))
        return (
            "⚠️ I'm having trouble connecting to my AI assistant right now.\n\n"
            "Please refer to the scheme details shared above, or try again in a moment."
        )


async def detect_language(text: str) -> str:
    """
    Simple heuristic language detection (Hindi vs English).

    Uses character range detection instead of LLM call for speed.
    """
    hindi_chars = 0
    total_chars = 0

    for char in text:
        if char.isalpha():
            total_chars += 1
            # Devanagari Unicode range
            if '\u0900' <= char <= '\u097F':
                hindi_chars += 1

    if total_chars == 0:
        return "en"

    # If more than 30% Devanagari characters, treat as Hindi
    if hindi_chars / total_chars > 0.3:
        return "hi"

    return "en"
