"""
Pre-built degradation scenarios for known demo verticals.

These are hardcoded — no AI call needed at demo time.
Currently supported: otel-demo (astroshop)

Each scenario dict is compatible with executor.run_scenario().
"""

from __future__ import annotations

# ── OTel Demo (astroshop) scenarios ───────────────────────────────────────────
# Maps directly to the 5 known feature flags in the OTel Demo feature flag service.
# Flag API: POST http://localhost:8013/feature-flag
# Body: {"name": "<flag>", "enabled": true|false}

OTEL_DEMO_SCENARIOS: list[dict] = [
    {
        "name": "Payment Service Failure",
        "service_name": "Payment Service",
        "failure_type": "service_error",
        "description": (
            "Activates the paymentServiceFailure feature flag, causing the Payment Service "
            "to return errors on all charge requests. Checkout flows will fail at the final step."
        ),
        "expected_impact": (
            "100% checkout failure rate. Cart Service and Checkout Service will show elevated "
            "error spans. Frontend will display payment error to users."
        ),
        "time_to_alert_seconds": 60,
        "otel_demo_flag": "paymentServiceFailure",
        "k8s_inject": [],
        "k8s_recover": [],
        "hec_events": [],
        "demo_talking_points": [
            "Watch the Checkout Service error rate spike in the Service Map within 60s",
            "Drill into a failing trace — Payment Service span shows ERROR status with exception detail",
            "ITSI health score for Payment Service will drop to red, triggering a Notable Event",
            "Correlation search fires an episode linking Payment + Checkout degradation",
            "Recovery is instant — disable the flag and the error rate clears within one polling cycle",
        ],
    },
    {
        "name": "Recommendation Service Cache Failure",
        "service_name": "Recommendation Service",
        "failure_type": "cache_miss",
        "description": (
            "Activates recommendationServiceCacheFailure, causing the Recommendation Service "
            "to bypass its in-memory cache and re-compute every request. CPU and latency spike."
        ),
        "expected_impact": (
            "Recommendation Service P95 latency increases 5-10x. CPU utilization spikes. "
            "Downstream callers (Frontend) will see slower page loads but no hard errors."
        ),
        "time_to_alert_seconds": 90,
        "otel_demo_flag": "recommendationServiceCacheFailure",
        "k8s_inject": [],
        "k8s_recover": [],
        "hec_events": [],
        "demo_talking_points": [
            "Latency degrades without hard errors — demonstrates the difference between error-based and latency-based alerting",
            "P95 latency KPI breaches yellow threshold before error rate moves",
            "Profiling (if enabled) will show the cache miss loop consuming CPU cycles",
            "Good demo of ITSI health scoring on a non-binary signal (latency vs error)",
        ],
    },
    {
        "name": "Cart Service Failure",
        "service_name": "Cart Service",
        "failure_type": "service_error",
        "description": (
            "Activates cartServiceFailure, causing the Cart Service to return errors. "
            "Users cannot add items to cart or view their cart."
        ),
        "expected_impact": (
            "Cart Service error rate hits 100%. Checkout Service is blocked — no purchases "
            "can complete. Frontend shows cart unavailable errors."
        ),
        "time_to_alert_seconds": 45,
        "otel_demo_flag": "cartServiceFailure",
        "k8s_inject": [],
        "k8s_recover": [],
        "hec_events": [],
        "demo_talking_points": [
            "Cart failure cascades to Checkout — demonstrates service dependency mapping in ITSI",
            "Cart Redis KPI should remain green (infra is fine — the app layer is failing)",
            "Split-brain scenario: Redis health OK, Cart Service health RED — good for showing tiered health",
            "Episode aggregation policy groups Cart + Checkout alerts into one incident",
        ],
    },
    {
        "name": "Product Catalog Service Error",
        "service_name": "Product Catalog Service",
        "failure_type": "service_error",
        "description": (
            "Activates productCatalogServiceError, injecting errors into Product Catalog "
            "responses. Product listing and detail pages fail intermittently."
        ),
        "expected_impact": (
            "~50% of product catalog requests fail. Homepage and product detail pages will "
            "show errors. Checkout may fail if product data cannot be fetched."
        ),
        "time_to_alert_seconds": 60,
        "otel_demo_flag": "productCatalogServiceError",
        "k8s_inject": [],
        "k8s_recover": [],
        "hec_events": [],
        "demo_talking_points": [
            "Intermittent errors (not 100%) — demonstrates threshold-based alerting vs binary",
            "Good example of a mid-funnel failure: browsing breaks before checkout",
            "Recommendation Service may also degrade (depends on catalog lookups)",
            "Trace Analyzer view shows ERROR spans scattered across a 50/50 mix of good/bad traces",
        ],
    },
    {
        "name": "Shipping Service Failure",
        "service_name": "Shipping Service",
        "failure_type": "service_error",
        "description": (
            "Activates shippingServiceFailure, causing the Shipping Service to return errors "
            "on all quote and dispatch requests. Checkout cannot calculate shipping costs."
        ),
        "expected_impact": (
            "Checkout flow fails at shipping quote step. Shipping Service shows 100% error rate. "
            "Payment Service remains healthy — demonstrates partial failure isolation."
        ),
        "time_to_alert_seconds": 45,
        "otel_demo_flag": "shippingServiceFailure",
        "k8s_inject": [],
        "k8s_recover": [],
        "hec_events": [],
        "demo_talking_points": [
            "Payment Service stays green while Shipping fails — good for root cause isolation demo",
            "Service map clearly shows the failure source: Checkout → Shipping span is red",
            "ITSI episode fires on Shipping Service, NOT on Checkout or Payment",
            "Demonstrates how ITSI avoids alert storms by identifying the root cause service",
        ],
    },
]

# Registry of hardcoded scenario sets by vertical name
VERTICAL_SCENARIOS: dict[str, list[dict]] = {
    "otel-demo": OTEL_DEMO_SCENARIOS,
}


def get_scenarios_for_vertical(vertical: str) -> list[dict] | None:
    """Return pre-built scenarios for a vertical, or None if not available."""
    return VERTICAL_SCENARIOS.get(vertical.lower().strip())


def list_scenario_verticals() -> list[str]:
    return list(VERTICAL_SCENARIOS.keys())
