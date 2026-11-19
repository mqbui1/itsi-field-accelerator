"""
AI-driven content pack enrichment.

Takes an existing ITSI content pack and uses Claude to:
1. Assess coverage gaps per service (step 1 — simple assessment schema)
2. Generate specific KPIs for undercovered services (step 2 — reuses kpi_generator)
3. Add missing services flagged by Claude

Two-step design avoids complex nested schemas that cause Claude to skip arrays.
"""

from __future__ import annotations

import json
from typing import Any

from itsi_accelerator.ai.claude_client import tool_call, stream_text

SYSTEM_ASSESS = """You are a senior Splunk ITSI architect reviewing a content pack for quality.

For each service, assess:
- Golden signal coverage (latency, errors, traffic, saturation)
- Whether the service needs more KPIs or is adequately covered
- Missing services that should exist in this architecture

Be specific. Services with only 0-1 non-health KPIs almost always need more coverage.
The top-level business service (monitoring_tier=business) is intentionally KPI-free —
its health rolls up from children, so mark it as no_change.
"""

ASSESS_TOOL = {
    "description": "Assess monitoring coverage gaps in an ITSI content pack",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-3 sentence overall assessment of the pack's coverage quality"
            },
            "coverage_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall monitoring coverage score (0=no coverage, 100=excellent)"
            },
            "services_needing_kpis": {
                "type": "array",
                "description": "Services that need additional KPI coverage",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "current_kpi_count": {"type": "integer"},
                        "missing_signals": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Golden signals missing, e.g. ['latency', 'saturation']"
                        },
                        "reason": {"type": "string"}
                    },
                    "required": ["name", "current_kpi_count", "missing_signals", "reason"]
                }
            },
            "missing_services": {
                "type": "array",
                "description": "Services that should exist but are missing from the pack",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "ci_type": {
                            "type": "string",
                            "enum": [
                                "web_server", "app_server", "database", "linux_host",
                                "kubernetes", "message_queue", "api_gateway",
                                "payment_processor", "fraud_detection", "auth_service",
                                "other"
                            ]
                        },
                        "parent": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["name", "ci_type", "parent", "reason"]
                }
            },
            "top_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top 3-5 monitoring gaps that remain after enrichment"
            }
        },
        "required": ["summary", "coverage_score", "services_needing_kpis", "missing_services", "top_gaps"]
    }
}


def enrich_pack(pack_dict: dict[str, Any], index: str = "main") -> dict[str, Any]:
    """
    Two-step enrichment:
    1. Claude assesses coverage gaps (simple schema, reliable output)
    2. kpi_generator fills gaps for each flagged service

    Returns an enrichment plan dict compatible with apply_enrichment().
    """
    from itsi_accelerator.ai.kpi_generator import generate_kpis

    services = pack_dict.get("data", {}).get("services", [])

    # Build compact representation for assessment
    compact = []
    for svc in services:
        kpi_titles = [
            k.get("title", "") for k in svc.get("kpis", [])
            if k.get("title") != "ServiceHealthScore"
        ]
        compact.append({
            "name": svc.get("title", ""),
            "description": svc.get("description", ""),
            "tags": svc.get("tags", []),
            "kpi_count": len(kpi_titles),
            "kpi_titles": kpi_titles,
        })

    # Step 1: assessment
    assessment = tool_call(
        system=SYSTEM_ASSESS,
        user=(
            f"Content pack: '{pack_dict.get('title', 'Unknown')}'\n"
            f"Splunk index: {index}\n"
            f"Services ({len(services)} total):\n"
            f"{json.dumps(compact, indent=2)}\n\n"
            "Identify which services need more KPI coverage and which services are missing entirely."
        ),
        tool_name="assess_coverage",
        tool_schema=ASSESS_TOOL,
        max_tokens=4096,
    )

    # Step 2: generate KPIs for each flagged service
    service_improvements = []
    name_to_svc = {s.get("title", ""): s for s in services}

    for flagged in assessment.get("services_needing_kpis", []):
        svc_name = flagged["name"]
        svc = name_to_svc.get(svc_name)
        if svc is None:
            continue

        # Infer ci_type from tags
        ci_type = next(
            (t for t in svc.get("tags", []) if t not in ("field-accelerator", "ai-discovered", "ai-suggested",
                                                           "business-service", "business", "application",
                                                           "platform", "infrastructure", "production")),
            "app_server"
        )

        try:
            kpi_result = generate_kpis(
                service_name=svc_name,
                service_description=svc.get("description", ""),
                ci_type=ci_type,
                index=index,
                sla_critical="sla_critical" in svc.get("tags", []),
            )
            new_kpis = kpi_result.get("kpis", [])
        except Exception:
            new_kpis = []

        service_improvements.append({
            "service_name": svc_name,
            "action": "add_kpis",
            "reason": flagged.get("reason", ""),
            "new_kpis": new_kpis,
        })

    # Combine into final enrichment plan
    return {
        "summary": assessment.get("summary", ""),
        "coverage_score": assessment.get("coverage_score", 0),
        "service_improvements": service_improvements,
        "missing_services": assessment.get("missing_services", []),
        "top_gaps": assessment.get("top_gaps", []),
    }


def apply_enrichment(pack_dict: dict[str, Any], enrichment: dict[str, Any], index: str = "main") -> dict[str, Any]:
    """Apply an enrichment plan to a content pack dict. Returns the modified pack."""
    from itsi_accelerator.core.models import new_id

    services = pack_dict.get("data", {}).get("services", [])
    name_to_svc = {s.get("title", ""): s for s in services}

    kpis_added = 0
    for improvement in enrichment.get("service_improvements", []):
        svc = name_to_svc.get(improvement.get("service_name", ""))
        if svc is None:
            continue

        existing_titles = {k.get("title", "") for k in svc.get("kpis", [])}
        for kpi_def in improvement.get("new_kpis", []):
            if kpi_def.get("title") in existing_titles:
                continue
            spl = kpi_def.get("base_search", "").replace("{index}", index)
            svc.setdefault("kpis", []).append({
                "_key": new_id(),
                "title": kpi_def.get("title", ""),
                "type": "search",
                "base_search": spl,
                "unit": kpi_def.get("unit", ""),
                "aggregate_statop": kpi_def.get("aggregate_statop", "avg"),
                "entity_statop": kpi_def.get("entity_statop", "avg"),
                "description": kpi_def.get("description", ""),
                "is_enabled": 1,
                "alert_period": 5,
                "alert_lag": 30,
                "threshold_template_id": "",
                "_enriched_by_ai": True,
            })
            kpis_added += 1

    # Add missing services
    for missing in enrichment.get("missing_services", []):
        name = missing.get("name", "")
        if name in name_to_svc:
            continue
        parent_name = missing.get("parent", "")
        new_svc = {
            "_key": new_id(),
            "title": name,
            "description": f"[AI-suggested] {missing.get('reason', '')}",
            "object_type": "service",
            "enabled": 1,
            "tags": ["field-accelerator", "ai-suggested", missing.get("ci_type", "")],
            "entity_rules": [],
            "services_depends_on": [],
            "kpis": [{
                "_key": new_id(),
                "title": "ServiceHealthScore",
                "type": "service_health",
                "base_search": "",
                "threshold_template_id": "",
                "is_enabled": 1,
                "alert_period": 5,
                "alert_lag": 30,
            }],
            "teams": [{"_key": "Global"}],
        }
        services.append(new_svc)
        name_to_svc[name] = new_svc
        parent_svc = name_to_svc.get(parent_name)
        if parent_svc:
            parent_svc.setdefault("services_depends_on", []).append(new_svc["_key"])

    pack_dict["data"]["services"] = services
    pack_dict["_enriched"] = True
    pack_dict["_coverage_score"] = enrichment.get("coverage_score", 0)
    pack_dict["_kpis_added"] = kpis_added
    return pack_dict


def review_pack(pack_dict: dict[str, Any]) -> str:
    """Stream a plain-text review of a content pack. Returns the full review text."""
    services = pack_dict.get("data", {}).get("services", [])
    compact = [
        {
            "name": s.get("title"),
            "kpis": [k.get("title") for k in s.get("kpis", []) if k.get("title") != "ServiceHealthScore"],
            "deps": len(s.get("services_depends_on", [])),
        }
        for s in services
    ]
    return stream_text(
        system="You are a senior Splunk ITSI architect providing a code review of a monitoring configuration.",
        user=(
            f"Content pack: '{pack_dict.get('title', 'Unknown')}'\n"
            f"Services:\n{json.dumps(compact, indent=2)}\n\n"
            "Provide a concise ITSI monitoring quality review covering: "
            "golden signal coverage, SPL quality concerns, missing services, "
            "dependency completeness, and your top 3 recommendations to improve this pack."
        ),
    )
