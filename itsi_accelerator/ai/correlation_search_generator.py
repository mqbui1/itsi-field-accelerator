"""
Batched AI-driven correlation search generation.

One Claude call generates correlation searches for all services at once,
keeping latency and API cost reasonable.

Each correlation search:
- Targets a specific failure condition for the service
- Produces a notable event that feeds ITSI episode management
- Includes runnable SPL with an itsi_event_generator-compatible output
"""

from __future__ import annotations

from itsi_accelerator.ai.claude_client import tool_call

SYSTEM = """You are a Splunk ITSI architect writing correlation searches for IT service monitoring.

Correlation searches in ITSI:
- Run on a schedule (every 5 minutes by default)
- Generate "notable events" when conditions are met
- Feed into NEAP episodes for incident management
- Must end with: | stats count as event_count by host | where event_count > 0

SPL rules:
1. Use `index={index}` as the index placeholder
2. The search MUST produce at least one result for the alert to fire
3. Keep searches efficient — use tstats where possible for metric-style data
4. Each search should detect ONE specific failure condition
5. End with a `| eval severity="<level>"` before the final stats

Severity levels: critical (service unavailable), high (degraded), medium (warning), low (informational)
"""

CORR_SEARCH_TOOL = {
    "description": "Generate ITSI correlation searches for a set of services",
    "input_schema": {
        "type": "object",
        "properties": {
            "correlation_searches": {
                "type": "array",
                "description": "List of correlation search definitions, 1-2 per non-business-service",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Name of the service this search monitors"
                        },
                        "name": {
                            "type": "string",
                            "description": "Search name: 'ITSI - {ServiceName} - {ConditionName}', e.g. 'ITSI - Payment API - High Error Rate'"
                        },
                        "description": {
                            "type": "string",
                            "description": "What condition this search detects and why it matters"
                        },
                        "search": {
                            "type": "string",
                            "description": "Full SPL search. Use {index} as the index placeholder. Must produce results when the alert condition is met."
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "description": "Alert severity when the search fires"
                        },
                        "alert_title": {
                            "type": "string",
                            "description": "Short event title shown in the ITSI episode, e.g. 'Payment API error rate exceeded 5%'"
                        },
                        "cron_schedule": {
                            "type": "string",
                            "description": "Cron schedule, e.g. '*/5 * * * *' for every 5 minutes"
                        }
                    },
                    "required": ["service_name", "name", "description", "search", "severity", "alert_title", "cron_schedule"]
                }
            }
        },
        "required": ["correlation_searches"]
    }
}


def generate_correlation_searches(
    services: list[dict],
    index: str = "main",
    context: str = "",
) -> list[dict]:
    """
    Generate correlation searches for all non-business services in one Claude call.

    Args:
        services: List of service dicts with keys: name, description, ci_type, kpis (optional)
        index: Splunk index to use in SPL
        context: Additional context (industry, compliance, etc.)

    Returns:
        List of correlation search dicts matching the CorrelationSearch model fields
    """
    # Exclude pure business services — they have no direct data, health rolls up from children
    target_services = [s for s in services if s.get("ci_type") != "business_service"]

    if not target_services:
        return []

    svc_lines = []
    for svc in target_services:
        kpis = svc.get("kpis", [])
        kpi_names = ", ".join(k.get("title", "") for k in kpis[:4]) if kpis else "none defined yet"
        line = (
            f"- {svc['name']} (type: {svc.get('ci_type', 'app_server')}, "
            f"sla_critical: {svc.get('sla_critical', False)}, "
            f"key_kpis: {kpi_names})"
        )
        svc_lines.append(line)

    prompt = (
        f"Generate ITSI correlation searches for these services. "
        f"Splunk index: {index}\n\n"
        "Services:\n" + "\n".join(svc_lines)
    )
    if context:
        prompt += f"\n\nContext: {context}"
    prompt += (
        "\n\nGenerate 1-2 correlation searches per service targeting the most critical "
        "failure conditions (error rate spike, unavailability, latency breach, saturation). "
        "Focus on the SLA-critical services first."
    )

    result = tool_call(
        system=SYSTEM,
        user=prompt,
        tool_name="create_correlation_searches",
        tool_schema=CORR_SEARCH_TOOL,
        max_tokens=8192,
    )
    return result.get("correlation_searches", [])
