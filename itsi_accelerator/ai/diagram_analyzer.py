"""
Architecture diagram → ITSI service tree via Claude vision.

Accepts PNG, JPEG, GIF, WEBP (Claude vision) or SVG (sent as XML text).
Returns the same structured service tree dict as service_discoverer.discover_services().
"""

from __future__ import annotations

import base64
from pathlib import Path

from itsi_accelerator.ai.claude_client import tool_call_with_image
from itsi_accelerator.ai.service_discoverer import SYSTEM, DISCOVER_TOOL

SUPPORTED_IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def analyze_diagram(image_path: str, context: str = "") -> dict:
    """
    Analyze an architecture diagram and return a structured ITSI service tree.

    Supports PNG, JPEG, GIF, WEBP (Claude vision) and SVG (as XML text).

    Args:
        image_path: Path to the diagram file
        context: Additional context (industry, stack, SLA requirements, etc.)

    Returns:
        Dict with 'services', 'architecture_summary', 'recommended_index', 'coverage_gaps'
        (same schema as service_discoverer.discover_services)
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Diagram file not found: {image_path}")

    suffix = path.suffix.lower()
    content = []

    if suffix == ".svg":
        svg_text = path.read_text(encoding="utf-8")
        content.append({
            "type": "text",
            "text": f"Here is an architecture diagram in SVG format:\n\n```svg\n{svg_text}\n```",
        })
    elif suffix in SUPPORTED_IMAGE_TYPES:
        media_type = SUPPORTED_IMAGE_TYPES[suffix]
        image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": image_data,
            },
        })
    else:
        supported = ", ".join(sorted(SUPPORTED_IMAGE_TYPES.keys()) + [".svg"])
        raise ValueError(f"Unsupported file format '{suffix}'. Supported: {supported}")

    prompt = (
        "Analyze this architecture diagram and generate a complete ITSI service tree. "
        "Identify all services, their call-path dependencies, technology types, and monitoring tiers."
    )
    if context:
        prompt += f"\n\nAdditional context: {context}"

    content.append({"type": "text", "text": prompt})

    return tool_call_with_image(
        system=SYSTEM,
        content=content,
        tool_name="create_service_tree",
        tool_schema=DISCOVER_TOOL,
    )
