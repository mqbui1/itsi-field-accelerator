"""
AI-driven content pack enrichment.

Takes an existing ITSI content pack (from cmdb or bootstrap) and uses Claude to:
1. Identify KPI coverage gaps per service
2. Improve generic template SPL with more targeted queries
3. Add missing dependency relationships
4. Recommend threshold values based on service criticality
5. Flag services with no KPIs or only the health score KPI

Also supports a "review" mode that returns a plain-text analysis without modifying the pack.
"""

from __future__ import annotations

import json
from typing import Any

from itsi_accelerator.ai.claude_client import tool_call, stream_text

SYSTEM = """You are a senior Splunk ITSI architect reviewing a content pack for quality and completeness.

You assess:
- KPI coverage: does each service have golden signal coverage (latency, errors, traffic, saturation)?
- SPL quality: is the search specific enough, or is it overly generic?
- Dependency completeness: are parent-child relationships accurately reflecting the architecture?
- Threshold calibration: are thresholds set, and are they appropriate for the service criticality?
- Missing services: are there obvious tiers or components not represented?

When suggesting improvements, be specific and actionable. For SPL improvements, write the actual
improved SPL, not just describe it. Keep suggestions realistic — don't recommend data that may
not exist without knowing the customer's setup.
"""

ENRICH_TOOL = {
    "description": "Return an enriched version of the content pack with improvements applied",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-3 sentence summary of the pack's current state and what was improved"
            },
            "service_improvements": {
                "type": "array",
                "description": "Per-service improvements",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": ["add_kpis", "improve_kpis", "update_description", "add_dependency", "no_change"],
                        },
                        "reason": {"type": "string", "description": "Why this improvement is needed"},
                        "new_kpis": {
                            "type": "array",
                            "description": "New KPIs to add (only when action=add_kpis or improve_kpis)",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "base_search": {"type": "string"},
                                    "metric": {"type": "string"},
                                    "unit": {"type": "string"},
                                    "aggregate_statop": {"type": "string"},
                                    "threshold_yellow": {"type": "number"},
                                    "threshold_red": {"type": "number"},
                                    "description": {"type": "string"},
                                    "golden_signal": {"type": "string"}
                                },
                                "required": ["title", "base_search", "metric", "unit", "aggregate_statop"]
                            }
                        },
                        "updated_description": {"type": "string", "description": "Improved service description (optional)"},
                        "new_dependency": {"type": "string", "description": "Name of service this should depend on (optional)"}
                    },
                    "required": ["service_name", "action", "reason"]
                }
            },
            "missing_services": {
                "type": "array",
                "description": "Services that should exist but are missing from the pack",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "ci_type": {"type": "string"},
                        "parent": {"type": "string"},
                        "reason": {"type": "string"}
                    },
                    "required": ["name", "ci_type", "parent", "reason"]
                }
            },
            "coverage_score": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall monitoring coverage score for the pack (0-100)"
            },
            "top_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Top 3-5 monitoring gaps that remain after enrichment"
            }
        },
        "required": ["summary", "service_improvements", "missing_services", "coverage_score", "top_gaps"]
    }
}


def enrich_pack(pack_dict: dict[str, Any], index: str = "main") -> dict[str, Any]:
    """
    Use Claude to analyze and improve a content pack dict.

    Returns an enrichment plan dict. Call apply_enrichment() to apply it.
    """
    services = pack_dict.get("data", {}).get("services", [])

    # Build a compact representation for Claude (avoid token bloat from full SPL)
    compact = []
    for svc in services:
        kpi_titles = [k.get("title", "") for k in svc.get("kpis", []) if k.get("title") != "ServiceHealthScore"]
        compact.append({
            "name": svc.get("title", ""),
            "description": svc.get("description", ""),
            "tags": svc.get("tags", []),
            "kpi_count": len(kpi_titles),
            "kpi_titles": kpi_titles,
            "has_dependencies": bool(svc.get("services_depends_on")),
        })

    prompt = (
        f"Content pack: '{pack_dict.get('title', 'Unknown')}'\n"
        f"Splunk index: {index}\n"
        f"Services ({len(services)} total):\n"
        f"{json.dumps(compact, indent=2)}\n\n"
        "Review this ITSI content pack and return a detailed enrichment plan. "
        "For each service, identify coverage gaps and provide improved or additional KPIs with real SPL. "
        "Also flag any missing services that should be in this architecture."
    )

    return tool_call(
        system=SYSTEM,
        user=prompt,
        tool_name="enrich_pack",
        tool_schema=ENRICH_TOOL,
        max_tokens=8192,
    )


def apply_enrichment(pack_dict: dict[str, Any], enrichment: dict[str, Any], index: str = "main") -> dict[str, Any]:
    """
    Apply an enrichment plan returned by enrich_pack() to a content pack dict.

    Returns the modified pack dict.
    """
    from itsi_accelerator.core.models import KPI, Service, new_id

    services = pack_dict.get("data", {}).get("services", [])
    name_to_svc = {s.get("title", ""): s for s in services}

    for improvement in enrichment.get("service_improvements", []):
        svc_name = improvement.get("service_name", "")
        svc = name_to_svc.get(svc_name)
        if svc is None:
            continue

        action = improvement.get("action", "no_change")

        if action in ("add_kpis", "improve_kpis"):
            for kpi_def in improvement.get("new_kpis", []):
                # Avoid duplicate KPI titles
                existing_titles = {k.get("title", "") for k in svc.get("kpis", [])}
                if kpi_def.get("title") in existing_titles:
                    continue
                spl = kpi_def.get("base_search", "").replace("{index}", index)
                new_kpi = {
                    "_key": new_id(),
                    "title": kpi_def.get("title", ""),
                    "type": "search",
                    "base_search": spl,
                    "metric": kpi_def.get("metric", ""),
                    "unit": kpi_def.get("unit", ""),
                    "aggregate_statop": kpi_def.get("aggregate_statop", "avg"),
                    "entity_statop": "avg",
                    "description": kpi_def.get("description", ""),
                    "is_enabled": 1,
                    "alert_period": 5,
                    "alert_lag": 30,
                    "threshold_template_id": "",
                    "_enriched_by_ai": True,
                }
                svc.setdefault("kpis", []).append(new_kpi)

        if action == "update_description" and improvement.get("updated_description"):
            svc["description"] = improvement["updated_description"]

    # Add missing services flagged by Claude
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
            "tags": ["field-accelerator", "ai-suggested"],
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

        # Wire dependency into parent if found
        parent_svc = name_to_svc.get(parent_name)
        if parent_svc:
            parent_svc.setdefault("services_depends_on", []).append(new_svc["_key"])

    pack_dict["data"]["services"] = services
    pack_dict["_enriched"] = True
    pack_dict["_coverage_score"] = enrichment.get("coverage_score", 0)

    return pack_dict


def review_pack(pack_dict: dict[str, Any]) -> str:
    """
    Stream a plain-text review of a content pack. Returns the full review text.
    """
    services = pack_dict.get("data", {}).get("services", [])
    compact = [
        {
            "name": s.get("title"),
            "kpis": [k.get("title") for k in s.get("kpis", []) if k.get("title") != "ServiceHealthScore"],
            "deps": len(s.get("services_depends_on", [])),
        }
        for s in services
    ]

    prompt = (
        f"Content pack: '{pack_dict.get('title', 'Unknown')}'\n"
        f"Services:\n{json.dumps(compact, indent=2)}\n\n"
        "Provide a concise ITSI monitoring quality review covering: "
        "golden signal coverage, SPL quality concerns, missing services, "
        "dependency completeness, and your top 3 recommendations to improve this pack."
    )

    return stream_text(
        system="You are a senior Splunk ITSI architect providing a code review of a monitoring configuration.",
        user=prompt,
    )
