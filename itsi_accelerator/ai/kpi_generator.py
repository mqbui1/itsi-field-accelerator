"""
AI-driven KPI generation.

Given a service's context (name, type, description, available sourcetypes/fields),
Claude generates custom KPI definitions with real SPL — not just template substitutions.

This produces KPIs that reflect the actual service and data, including:
- SPL tailored to the specific sourcetype/field schema
- Thresholds calibrated to the service's criticality
- Business-relevant metric names (not just generic "error rate")
"""

from __future__ import annotations

from itsi_accelerator.ai.claude_client import tool_call

SYSTEM = """You are a Splunk ITSI KPI expert and SPL author with deep knowledge of:
- ITSI KPI base searches and threshold templates
- Splunk SPL best practices for metric KPIs
- Industry-standard SLIs for different service types
- Golden signal monitoring (latency, traffic, errors, saturation)

When generating KPIs:
1. Write SPL that is syntactically correct and runnable
2. Use `stats` or `tstats` commands — KPIs need a single numeric output
3. Scale thresholds to the service criticality (SLA-critical = tighter thresholds)
4. Cover all four golden signals where data supports it
5. Add business-context KPIs for SLA-critical services (not just infra metrics)
6. Keep SPL efficient — avoid expensive operations like `transaction` where possible
7. Use `index={index}` as the index placeholder — it will be substituted at runtime
8. If the service has specific sourcetypes, use them; otherwise write broadly applicable SPL

SPL must end with `| stats <agg>(<metric_field>) as <metric_name> by <entity_field>`
so ITSI can extract the numeric value and entity breakdown.
"""

KPI_TOOL = {
    "description": "Generate ITSI KPI definitions with SPL for a service",
    "input_schema": {
        "type": "object",
        "properties": {
            "kpis": {
                "type": "array",
                "description": "List of KPI definitions for this service",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "KPI name shown in ITSI UI, e.g. 'HTTP Error Rate (%)'"},
                        "description": {"type": "string", "description": "What this KPI measures and why it matters for this service"},
                        "base_search": {"type": "string", "description": "Full SPL base search. Use {index} as index placeholder."},
                        "metric": {"type": "string", "description": "Output field name from the SPL stats command"},
                        "unit": {"type": "string", "description": "Unit label, e.g. %, ms, req/s, count"},
                        "aggregate_statop": {
                            "type": "string",
                            "enum": ["avg", "max", "min", "sum", "median", "stdev", "count"],
                            "description": "How to aggregate across entities"
                        },
                        "entity_statop": {
                            "type": "string",
                            "enum": ["avg", "max", "min", "sum", "median"],
                            "description": "How to aggregate per entity over time"
                        },
                        "threshold_yellow": {"type": "number", "description": "Warning threshold value, or null for adaptive"},
                        "threshold_red": {"type": "number", "description": "Critical threshold value, or null for adaptive"},
                        "threshold_direction": {
                            "type": "string",
                            "enum": ["above", "below"],
                            "description": "'above' means breach when value exceeds threshold (error rates); 'below' means breach when value drops below (availability)"
                        },
                        "golden_signal": {
                            "type": "string",
                            "enum": ["latency", "traffic", "errors", "saturation", "availability", "business"],
                            "description": "Which golden signal category this KPI covers"
                        },
                        "sla_relevant": {"type": "boolean", "description": "True if this KPI directly contributes to SLA compliance"}
                    },
                    "required": [
                        "title", "description", "base_search", "metric", "unit",
                        "aggregate_statop", "entity_statop", "threshold_direction",
                        "golden_signal", "sla_relevant"
                    ]
                }
            },
            "coverage_note": {
                "type": "string",
                "description": "Brief note on KPI coverage — what's well covered, any gaps"
            }
        },
        "required": ["kpis", "coverage_note"]
    }
}


def generate_kpis(
    service_name: str,
    service_description: str,
    ci_type: str,
    index: str = "main",
    sourcetypes: list[str] | None = None,
    fields: list[str] | None = None,
    sla_critical: bool = False,
    industry_context: str = "",
) -> dict:
    """
    Generate custom KPI definitions for a service using Claude.

    Returns dict with 'kpis' list and 'coverage_note'.
    """
    parts = [
        f"Service: {service_name}",
        f"Type: {ci_type}",
        f"Description: {service_description}",
        f"Splunk index: {index}",
        f"SLA-critical: {sla_critical}",
    ]
    if sourcetypes:
        parts.append(f"Available sourcetypes: {', '.join(sourcetypes)}")
    if fields:
        parts.append(f"Known fields: {', '.join(fields)}")
    if industry_context:
        parts.append(f"Industry/context: {industry_context}")

    parts.append(
        "\nGenerate 4-6 KPIs for this service covering the golden signals. "
        "Write real, runnable SPL tailored to this service type. "
        + ("This is SLA-critical — use tight thresholds and include business KPIs." if sla_critical else "")
    )

    return tool_call(
        system=SYSTEM,
        user="\n".join(parts),
        tool_name="create_kpis",
        tool_schema=KPI_TOOL,
        max_tokens=4096,
    )
