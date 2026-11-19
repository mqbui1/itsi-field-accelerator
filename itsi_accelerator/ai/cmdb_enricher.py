"""
AI-powered CMDB CI type inference.

When a CMDB export has missing, unknown, or generic CI class names,
Claude infers the correct service type from the CI's name and description.

Also handles bulk enrichment of a row list before passing to the CMDB parser.
"""

from __future__ import annotations

from itsi_accelerator.ai.claude_client import tool_call
from itsi_accelerator.templates.kpi_library import CI_CLASS_ALIASES

KNOWN_TYPES = list(set(CI_CLASS_ALIASES.values()))

SYSTEM = """You are a CMDB data analyst. Given a list of CIs (configuration items) with names
and descriptions, infer the correct service type for each one so ITSI KPI templates can be applied.

Base your inference on:
- The CI name (e.g. "payments-api" -> api_gateway or app_server)
- The description if present
- Common naming conventions in enterprise IT

Always pick the most specific type that fits. When uncertain between two types, pick the one
that would have more meaningful KPIs (e.g. prefer payment_processor over app_server for a payments service).
"""

INFER_TOOL = {
    "description": "Infer service types for a list of CIs",
    "input_schema": {
        "type": "object",
        "properties": {
            "inferences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "inferred_ci_type": {
                            "type": "string",
                            "enum": [
                                "web_server", "app_server", "database", "linux_host",
                                "kubernetes", "message_queue", "api_gateway",
                                "payment_processor", "fraud_detection", "auth_service",
                                "business_service", "cache", "other"
                            ]
                        },
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["name", "inferred_ci_type", "confidence", "reasoning"]
                }
            }
        },
        "required": ["inferences"]
    }
}


def infer_ci_types(rows: list[dict]) -> list[dict]:
    """
    For rows with missing/generic ci_class, ask Claude to infer the type.
    Returns the rows with ci_class filled in where missing.
    """
    needs_inference = [
        r for r in rows
        if not r.get("ci_class") or r.get("ci_class", "").lower() in (
            "", "cmdb_ci_service", "other", "unknown", "generic"
        )
    ]

    if not needs_inference:
        return rows

    ci_list = [
        {"name": r.get("name", ""), "description": r.get("description", "")}
        for r in needs_inference
    ]

    result = tool_call(
        system=SYSTEM,
        user=(
            f"Infer the service type for each of these CIs:\n"
            f"{chr(10).join(f'- {c[\"name\"]}: {c[\"description\"]}' for c in ci_list)}\n\n"
            f"Available types: {', '.join(KNOWN_TYPES)}"
        ),
        tool_name="infer_ci_types",
        tool_schema=INFER_TOOL,
        max_tokens=2048,
    )

    # Build a lookup from name -> inferred type
    inference_map = {
        inf["name"]: inf["inferred_ci_type"]
        for inf in result.get("inferences", [])
    }

    # Apply inferences to the rows
    enriched = []
    for row in rows:
        r = dict(row)
        name = r.get("name", "")
        if name in inference_map and (not r.get("ci_class") or r.get("ci_class") in ("", "cmdb_ci_service", "other", "unknown")):
            r["ci_class"] = inference_map[name]
            r["_ci_type_inferred"] = True
        enriched.append(r)

    return enriched
