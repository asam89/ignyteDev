"""
Dual LLM wrapper — supports both Claude (Anthropic) and Gemini (Google).
Selects provider based on config; falls back to the other if one fails.
"""

import os
import logging

import anthropic
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# Provider setup
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

_claude_client = None
_gemini_model = None


def _get_claude():
    global _claude_client
    if _claude_client is None and ANTHROPIC_API_KEY:
        _claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _claude_client


def _get_gemini():
    global _gemini_model
    if _gemini_model is None and GEMINI_API_KEY:
        _gemini_model = genai.GenerativeModel("gemini-2.5-flash-preview-05-20")
    return _gemini_model


def call_llm(
    prompt: str,
    system: str = "",
    provider: str = "auto",
    max_tokens: int = 4096,
) -> str:
    """
    Call an LLM and return the response text.

    provider: "claude", "gemini", or "auto" (tries claude first, then gemini).
    """
    if provider == "auto":
        providers = []
        if ANTHROPIC_API_KEY:
            providers.append("claude")
        if GEMINI_API_KEY:
            providers.append("gemini")
        if not providers:
            raise ValueError("No LLM API keys configured (ANTHROPIC_API_KEY or GEMINI_API_KEY)")
    else:
        providers = [provider]

    last_error = None
    for p in providers:
        try:
            if p == "claude":
                return _call_claude(prompt, system, max_tokens)
            elif p == "gemini":
                return _call_gemini(prompt, system, max_tokens)
            else:
                raise ValueError(f"Unknown LLM provider: {p}")
        except Exception as e:
            log.warning(f"LLM call failed with {p}: {e}")
            last_error = e
            continue

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


def _call_claude(prompt: str, system: str, max_tokens: int) -> str:
    client = _get_claude()
    if not client:
        raise ValueError("Claude not configured (missing ANTHROPIC_API_KEY)")

    kwargs = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    message = client.messages.create(**kwargs)
    return message.content[0].text.strip()


def _call_gemini(prompt: str, system: str, max_tokens: int) -> str:
    model = _get_gemini()
    if not model:
        raise ValueError("Gemini not configured (missing GEMINI_API_KEY)")

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    response = model.generate_content(
        full_prompt,
        generation_config={"max_output_tokens": max_tokens},
    )
    return response.text.strip()


def available_providers() -> list[str]:
    """Return list of configured LLM providers."""
    providers = []
    if ANTHROPIC_API_KEY:
        providers.append("claude")
    if GEMINI_API_KEY:
        providers.append("gemini")
    return providers
