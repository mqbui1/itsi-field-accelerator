"""
AI-driven degradation scenario generation.

Given a list of services from a content pack, Claude generates realistic failure
scenarios for each service: what breaks, how to inject it (k8s or HEC), what
KPIs will breach, and how to recover.

One Claude call returns all scenarios — batched for speed.
"""

from __future__ import annotations

from itsi_accelerator.ai.claude_client import tool_call

SYSTEM = """You are a senior SRE and Splunk ITSI demo engineer.

Your job is to generate realistic failure scenarios for IT services running in Kubernetes.
Each scenario must:
1. Be injected via kubectl commands (scale down, delete pod, exec stress) OR Splunk HEC events
2. Auto-recover cleanly via a matching recovery command
3. Directly cause the service's KPIs to breach in ITSI within 1-2 minutes
4. Tell the demo engineer exactly what they will see in ITSI

Failure types:
- unavailable: scale replicas to 0 (clean, instant, recoverable)
- high_error_rate: repeatedly delete pods (causes restarts + 5xx during restart), or inject via app feature flag
- high_latency: exec a stress --cpu command inside the pod for the duration
- cascade: take down a shared dependency (database, cache) to degrade multiple services at once

kubectl command tips:
- Always use the {namespace} placeholder for namespace
- Always use the {kubeconfig} placeholder for kubeconfig path
- Use label selectors like app=<service> or app.kubernetes.io/component=<service>
- Scale commands: kubectl scale deployment/<name> -n {namespace} --replicas=<n>
- Exec stress: kubectl exec -n {namespace} deploy/<name> -- sh -c "stress --cpu 4 --timeout {duration}s || true"
- Pod delete loop for error rate: kubectl delete pods -n {namespace} -l app=<service> --grace-period=0

For the OpenTelemetry Demo app (astroshop), use the feature flag API endpoint:
  POST http://<featureflag-host>:8013/feature-flag
  Body: {"name": "<FlagName>", "enabled": true}
  Known flags: paymentServiceFailure, recommendationServiceCacheFailure,
               cartServiceFailure, productCatalogServiceError, shippingServiceFailure

For HEC events, send log-like events that your correlation searches would detect.
"""

SCENARIO_TOOL = {
    "description": "Generate realistic degradation scenarios for ITSI demo services",
    "input_schema": {
        "type": "object",
        "properties": {
            "scenarios": {
                "type": "array",
                "description": "2-4 scenarios total — prioritize SLA-critical services and cascade effects",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Name of the target service (must match content pack service name)"
                        },
                        "name": {
                            "type": "string",
                            "description": "Short scenario name, e.g. 'Payment API - Unavailable'"
                        },
                        "description": {
                            "type": "string",
                            "description": "What this scenario simulates and why it's demo-worthy"
                        },
                        "failure_type": {
                            "type": "string",
                            "enum": ["unavailable", "high_error_rate", "high_latency", "cascade"],
                            "description": "Category of failure"
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "high", "medium"],
                            "description": "Expected episode severity in ITSI"
                        },
                        "expected_impact": {
                            "type": "string",
                            "description": "What the demo audience will see in ITSI (which services go red, what cascades)"
                        },
                        "expected_kpis_breached": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "KPI titles that will breach thresholds"
                        },
                        "time_to_alert_seconds": {
                            "type": "integer",
                            "description": "Estimated seconds until ITSI shows a notable event (typically 60-300)"
                        },
                        "k8s_inject": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "kubectl commands to inject the failure. Use {namespace} and {kubeconfig} placeholders."
                        },
                        "k8s_recover": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "kubectl commands to recover. Must fully undo the injection."
                        },
                        "hec_events": {
                            "type": "array",
                            "description": "Sample Splunk HEC event payloads to send (alternative to k8s injection)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sourcetype": {"type": "string"},
                                    "event": {"type": "object"}
                                }
                            }
                        },
                        "otel_demo_flag": {
                            "type": "string",
                            "description": "OTel demo feature flag name if applicable (e.g. paymentServiceFailure), empty string if not"
                        },
                        "demo_talking_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3-4 bullet points for the SA to narrate while the scenario runs"
                        }
                    },
                    "required": [
                        "service_name", "name", "description", "failure_type", "severity",
                        "expected_impact", "expected_kpis_breached", "time_to_alert_seconds",
                        "k8s_inject", "k8s_recover", "hec_events", "otel_demo_flag",
                        "demo_talking_points"
                    ]
                }
            }
        },
        "required": ["scenarios"]
    }
}


def generate_scenarios(
    services: list[dict],
    context: str = "",
    max_scenarios: int = 4,
) -> list[dict]:
    """
    Generate demo degradation scenarios for a set of services.

    Args:
        services: Service dicts from the content pack (name, ci_type, sla_critical, kpis)
        context: Additional context (industry, app name, k8s setup, etc.)
        max_scenarios: Maximum number of scenarios to generate

    Returns:
        List of scenario dicts matching the scenario schema
    """
    svc_lines = []
    for svc in services:
        kpi_names = ", ".join(k.get("title", "") for k in svc.get("kpis", [])[:4])
        line = (
            f"- {svc['name']} (type: {svc.get('ci_type', 'app_server')}, "
            f"sla_critical: {svc.get('sla_critical', False)}"
            + (f", kpis: {kpi_names}" if kpi_names else "")
            + ")"
        )
        svc_lines.append(line)

    prompt = (
        f"Generate {max_scenarios} demo degradation scenarios for these ITSI services:\n\n"
        + "\n".join(svc_lines)
    )
    if context:
        prompt += f"\n\nContext: {context}"
    prompt += (
        "\n\nPrioritize: (1) a cascade scenario that takes down a shared dependency, "
        "(2) a critical SLA-impacting service going unavailable, "
        "(3) a subtle degradation (high latency or error rate) that's harder to spot. "
        "Make each scenario demo-worthy — the audience should clearly see ITSI detecting it."
    )

    result = tool_call(
        system=SYSTEM,
        user=prompt,
        tool_name="create_scenarios",
        tool_schema=SCENARIO_TOOL,
        max_tokens=8192,
    )
    return result.get("scenarios", [])
