"""
Anthropic Claude client wrapper with tool_use support for structured ITSI generation.

Reads ANTHROPIC_API_KEY from env or ~/Documents/anthropicapikey.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic

MODEL = "claude-sonnet-4-6"
_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is not None:
        return _client

    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        keyfile = Path.home() / "Documents" / "anthropicapikey"
        if keyfile.exists():
            key = keyfile.read_text().strip().split("\n")[0]

    if not key:
        raise RuntimeError(
            "No Anthropic API key found. Set ANTHROPIC_API_KEY or create ~/Documents/anthropicapikey."
        )

    _client = anthropic.Anthropic(api_key=key)
    return _client


def tool_call(
    system: str,
    user: str,
    tool_name: str,
    tool_schema: dict,
    model: str = MODEL,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """
    Run a single Claude call with one tool and return the tool_use input dict.
    Uses tool_choice={"type": "tool"} to force Claude to always fill the schema.
    """
    client = get_client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[{"name": tool_name, "description": tool_schema["description"], "input_schema": tool_schema["input_schema"]}],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"Claude did not invoke tool '{tool_name}'. Response: {resp}")


def stream_text(system: str, user: str, model: str = MODEL) -> str:
    """Stream a plain-text response and return the full text."""
    client = get_client()
    full = []
    with client.messages.stream(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full.append(text)
    print()
    return "".join(full)
