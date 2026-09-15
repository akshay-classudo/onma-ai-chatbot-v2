"""
Thin wrapper around one LLM provider's chat-completions API.
Provider-specific request/response shape lives only here — swapping
providers (or moving to an EU-hosted one later) means editing this file only.

API key/model/endpoint can be overridden per-request from the BotSettings
admin singleton (bot/settings_store.py) without a restart — see
_chat_config()/_embedding_config() below, which resolve DB-over-.env.
"""

import json

import requests
from django.conf import settings

from .settings_store import get_bot_settings, resolve

FALLBACK_REPLIES = {
    "de": (
        "Entschuldigung, ich habe dazu momentan keine Information. Bitte "
        "kontaktieren Sie ONMA scout direkt, wir helfen Ihnen gerne "
        "persönlich weiter."
    ),
    "en": (
        "Sorry, I don't have that information right now. Please contact "
        "ONMA scout directly — we're happy to help you in person."
    ),
}


class LlmError(Exception):
    pass


def _chat_config():
    bot_settings = get_bot_settings()
    api_key = resolve(bot_settings.llm_api_key if bot_settings else "", settings.LLM_API_KEY)
    model = resolve(bot_settings.llm_model if bot_settings else "", settings.LLM_MODEL)
    endpoint = resolve(bot_settings.llm_endpoint if bot_settings else "", settings.LLM_ENDPOINT)
    return api_key, model, endpoint


def _embedding_config():
    bot_settings = get_bot_settings()
    api_key = resolve(bot_settings.llm_api_key if bot_settings else "", settings.LLM_API_KEY)
    model = resolve(bot_settings.embedding_model if bot_settings else "", settings.EMBEDDING_MODEL)
    endpoint = resolve(bot_settings.embedding_endpoint if bot_settings else "", settings.EMBEDDING_ENDPOINT)
    return api_key, model, endpoint


def chat_completion(messages: list[dict]) -> str:
    api_key, model, endpoint = _chat_config()
    if not api_key:
        raise LlmError("LLM API key is not configured")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 500,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=25)
    except requests.RequestException as exc:
        raise LlmError(f"LLM request failed: {exc}") from exc

    if not response.ok:
        raise LlmError(f"LLM request returned HTTP {response.status_code}: {response.text}")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LlmError("LLM response missing content") from exc

    if not content:
        raise LlmError("LLM response missing content")

    return content.strip()


def stream_chat_completion(messages: list[dict]):
    """Generator yielding text deltas as they arrive (OpenAI-compatible SSE
    chat-completions streaming format: lines of `data: {...}`, terminated by
    `data: [DONE]`). Raises LlmError up front for anything that fails before
    the first byte — request setup, auth, HTTP status; once streaming has
    started, a malformed individual line is skipped rather than aborting the
    whole reply."""
    api_key, model, endpoint = _chat_config()
    if not api_key:
        raise LlmError("LLM API key is not configured")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 500,
        "stream": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=60, stream=True)

        if not response.ok:
            raise LlmError(f"LLM request returned HTTP {response.status_code}: {response.text}")

        # requests defaults to Latin-1 for text/event-stream (no charset in the
        # response's Content-Type header), which silently mangles any non-ASCII
        # character — force UTF-8, since every OpenAI-compatible provider
        # actually sends UTF-8 regardless of what the header omits.
        response.encoding = "utf-8"

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue

            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break

            try:
                chunk = json.loads(data)
                content = chunk["choices"][0]["delta"].get("content")
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

            if content:
                yield content
    except requests.RequestException as exc:
        # Covers the initial connection AND any hiccup mid-stream (timeout,
        # dropped connection, chunked-encoding error from the provider) —
        # without this, an error here would escape the caller's `except
        # LlmError` in views.py, leaving the SSE response open with no
        # closing "done" frame and the browser's fetch hanging forever
        # (isSending stuck true, input permanently disabled).
        raise LlmError(f"LLM request failed: {exc}") from exc


def embed_texts(texts: list[str]) -> list[list[float]]:
    api_key, model, endpoint = _embedding_config()
    if not api_key:
        raise LlmError("LLM API key is not configured")

    if not texts:
        return []

    payload = {"model": model, "input": texts}
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=25)
    except requests.RequestException as exc:
        raise LlmError(f"Embedding request failed: {exc}") from exc

    if not response.ok:
        raise LlmError(f"Embedding request returned HTTP {response.status_code}: {response.text}")

    try:
        items = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]
    except (KeyError, IndexError, ValueError) as exc:
        raise LlmError("Embedding response missing data") from exc
