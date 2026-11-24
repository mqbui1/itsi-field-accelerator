"""
Template-based NEAP (Notable Event Aggregation Policy) generation.

No AI call needed — the NEAP structure is formulaic:
  - One NEAP per top-level business service
  - Aggregates notables from that service and its descendants
  - Breaks episode after configurable silence window
  - Optional AI-RCA trigger action

This aligns with the goal of encoding patterns into the framework itself
rather than depending on Claude at runtime.
"""

from __future__ import annotations

from itsi_accelerator.core.models import NotableEventAggregationPolicy, Service


def build_neaps(
    services: list[Service],
    break_after_silence_minutes: int = 15,
) -> list[NotableEventAggregationPolicy]:
    """
    Generate one NEAP per top-level business service (no parent dependencies).

    For services that aren't aggregator-level, generate a simple per-service NEAP
    so every service has at least one episode policy.

    Args:
        services: All Service objects from the content pack
        break_after_silence_minutes: Episode breaks after this many minutes of silence

    Returns:
        List of NotableEventAggregationPolicy objects
    """
    neaps = []
    # Service keys that are depended on by others (i.e. parent services)
    all_child_keys: set[str] = set()
    for svc in services:
        all_child_keys.update(svc.services_depends_on)

    for svc in services:
        is_root = svc._key not in all_child_keys  # not a child of anything = root/top-level
        neap = NotableEventAggregationPolicy(
            title=f"Episode: {svc.title}",
            description=(
                f"Aggregates notable events for the '{svc.title}' service. "
                f"Episodes break after {break_after_silence_minutes} minutes of silence."
            ),
            service_key=svc._key,
            break_after_silence_minutes=break_after_silence_minutes,
            split_by_field="service_id" if is_root else "host",
        )
        neaps.append(neap)

    return neaps
