"""
AI-driven service discovery.

Takes a free-text description of an application/architecture and returns a
structured ITSI service tree — services, dependencies, CI types, and entity rules.

This is the core "blank canvas -> populated ITSI" flow, powered by Claude.
"""

from __future__ import annotations

from itsi_accelerator.ai.claude_client import tool_call

SYSTEM = """You are a senior Splunk ITSI architect with deep expertise in service modeling.

Given a description of an application or infrastructure, you generate an ITSI service tree
following ITSI best practices:
- One top-level business service (the user-facing outcome)
- Logical tier services underneath (web, app, data, messaging, etc.)
- Infrastructure services as leaf nodes where relevant
- Dependency relationships that reflect real call paths (not org structure)
- Sensible CI types so KPI templates can be matched downstream

ITSI service modeling rules:
- Services represent monitoring domains, not teams or components
- Each service should be independently monitorable
- Parent services aggregate health from children
- Leaf services map to specific technology stacks
- Keep trees shallow (3-4 levels max) unless the app truly warrants depth
- Always include an auth/identity service if the app has user-facing login
"""

DISCOVER_TOOL = {
    "description": "Output a structured ITSI service tree from an architecture description",
    "input_schema": {
        "type": "object",
        "properties": {
            "services": {
                "type": "array",
                "description": "Ordered list of services — parent before children",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Human-readable service name, e.g. 'Payment Processing'"},
                        "description": {"type": "string", "description": "One sentence: what this service does and why it matters"},
                        "ci_type": {
                            "type": "string",
                            "enum": [
                                "web_server", "app_server", "database", "linux_host",
                                "kubernetes", "message_queue", "api_gateway",
                                "payment_processor", "fraud_detection", "auth_service",
                                "business_service", "cache", "search_engine",
                                "storage", "cdn", "load_balancer", "ml_platform",
                                "data_warehouse", "streaming", "other"
                            ],
                            "description": "Service type for KPI template matching"
                        },
                        "parent": {"type": "string", "description": "Name of the parent service, or empty string for the root"},
                        "business_service": {"type": "string", "description": "Name of the top-level business service this belongs to"},
                        "entity_field": {"type": "string", "description": "Splunk field to use as entity identifier, e.g. 'host', 'namespace', 'service_name'"},
                        "monitoring_tier": {
                            "type": "string",
                            "enum": ["business", "application", "platform", "infrastructure"],
                            "description": "Tier this service belongs to"
                        },
                        "sla_critical": {"type": "boolean", "description": "True if this service directly impacts user-facing SLA"}
                    },
                    "required": ["name", "description", "ci_type", "parent", "business_service", "monitoring_tier", "sla_critical"]
                }
            },
            "architecture_summary": {
                "type": "string",
                "description": "2-3 sentence summary of the architecture and monitoring strategy"
            },
            "recommended_index": {
                "type": "string",
                "description": "Best guess at the primary Splunk index (main, prod, app_logs, etc.)"
            },
            "coverage_gaps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of monitoring gaps or missing data sources the user should address"
            }
        },
        "required": ["services", "architecture_summary", "recommended_index", "coverage_gaps"]
    }
}


def discover_services(description: str, context: str = "") -> dict:
    """
    Given a free-text architecture description, return a structured service tree dict.

    Args:
        description: Architecture/application description from the user
        context: Optional additional context (industry, compliance requirements, etc.)

    Returns:
        Dict with 'services', 'architecture_summary', 'recommended_index', 'coverage_gaps'
    """
    prompt_parts = [f"Architecture description:\n{description}"]
    if context:
        prompt_parts.append(f"\nAdditional context:\n{context}")
    prompt_parts.append(
        "\nGenerate a complete ITSI service tree for this architecture. "
        "Include all tiers from business service down to infrastructure."
    )

    return tool_call(
        system=SYSTEM,
        user="\n".join(prompt_parts),
        tool_name="create_service_tree",
        tool_schema=DISCOVER_TOOL,
    )
