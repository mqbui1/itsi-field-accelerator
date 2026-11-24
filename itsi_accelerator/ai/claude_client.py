"""
Anthropic Claude client wrapper with tool_use support for structured ITSI generation.

Provider selection (checked in order):
  1. ITSI_AI_PROVIDER=anthropic|bedrock  — explicit override
  2. ANTHROPIC_API_KEY present           — use Anthropic direct API
  3. fallback                            — use AWS Bedrock (standard AWS credential chain)

Bedrock model (default: us.anthropic.claude-3-5-sonnet-20241022-v2:0):
  Override with BEDROCK_MODEL_ID env var.
  Region: AWS_DEFAULT_REGION or AWS_REGION (defaults to us-east-1).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anthropic

# Default models per provider
MODEL_ANTHROPIC = "claude-sonnet-4-6"
MODEL_BEDROCK = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

_client: anthropic.Anthropic | anthropic.AnthropicBedrock | None = None
_active_model: str | None = None


def _resolve_provider() -> str:
    """Return 'anthropic' or 'bedrock' based on env configuration."""
    explicit = os.environ.get("ITSI_AI_PROVIDER", "").lower()
    if explicit in ("anthropic", "bedrock"):
        return explicit
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    keyfile = Path.home() / "Documents" / "anthropicapikey"
    if keyfile.exists() and keyfile.read_text().strip():
        return "anthropic"
    return "bedrock"


def get_client() -> anthropic.Anthropic | anthropic.AnthropicBedrock:
    global _client, _active_model
    if _client is not None:
        return _client

    provider = _resolve_provider()

    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            keyfile = Path.home() / "Documents" / "anthropicapikey"
            if keyfile.exists():
                key = keyfile.read_text().strip().split("\n")[0]
        if not key:
            raise RuntimeError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY or create ~/Documents/anthropicapikey. "
                "To use AWS Bedrock instead, set ITSI_AI_PROVIDER=bedrock."
            )
        _client = anthropic.Anthropic(api_key=key)
        _active_model = MODEL_ANTHROPIC
    else:
        # Bedrock — uses standard AWS credential chain (env vars, ~/.aws/credentials, IAM role)
        region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
        try:
            _client = anthropic.AnthropicBedrock(aws_region=region)
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialise AWS Bedrock client: {e}\n"
                "Ensure AWS credentials are configured (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY, "
                "AWS_PROFILE, or an IAM role). Set ITSI_AI_PROVIDER=anthropic to use the Anthropic API instead."
            ) from e
        _active_model = os.environ.get("BEDROCK_MODEL_ID", MODEL_BEDROCK)

    return _client


def get_model() -> str:
    """Return the active model ID (resolves lazily on first call)."""
    if _active_model is None:
        get_client()
    return _active_model  # type: ignore[return-value]


def tool_call(
    system: str,
    user: str,
    tool_name: str,
    tool_schema: dict,
    model: str | None = None,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """
    Run a single Claude call with one tool and return the tool_use input dict.
    Uses tool_choice={"type": "tool"} to force Claude to always fill the schema.
    """
    client = get_client()
    active_model = model or get_model()
    resp = client.messages.create(
        model=active_model,
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


def tool_call_with_image(
    system: str,
    content: list,
    tool_name: str,
    tool_schema: dict,
    model: str | None = None,
    max_tokens: int = 8192,
) -> dict[str, Any]:
    """
    Like tool_call but accepts a pre-built content list (text + image blocks).
    Used for vision-based inputs (architecture diagrams, etc.).
    """
    client = get_client()
    active_model = model or get_model()
    resp = client.messages.create(
        model=active_model,
        max_tokens=max_tokens,
        system=system,
        tools=[{"name": tool_name, "description": tool_schema["description"], "input_schema": tool_schema["input_schema"]}],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": content}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input
    raise RuntimeError(f"Claude did not invoke tool '{tool_name}'. Response: {resp}")


def stream_text(system: str, user: str, model: str | None = None) -> str:
    """Stream a plain-text response and return the full text."""
    client = get_client()
    active_model = model or get_model()
    full = []
    with client.messages.stream(
        model=active_model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            full.append(text)
    print()
    return "".join(full)
