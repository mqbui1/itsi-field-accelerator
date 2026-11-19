"""
Curated KPI template library for common service/CI types.

Each entry maps a service_type (CI class name or semantic type) to a list of KPI dicts.
SPL is written as parameterized templates — `{index}` and `{host_filter}` are substituted
at generation time.

Sources:
- ITSI shipped KPI base search library (SA-ITOA kpi_base_search templates)
- Field-curated additions from customer engagements
"""

from __future__ import annotations

KPI_TEMPLATES: dict[str, list[dict]] = {

    # ── Web / HTTP tier ────────────────────────────────────────────────────
    "web_server": [
        {
            "title": "HTTP Error Rate (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=access_combined '
                '| eval is_error=if(status>=400,1,0) '
                '| stats count as total, sum(is_error) as errors by host '
                '| eval error_pct=round(errors/total*100,2)'
            ),
            "metric": "error_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "description": "Percentage of HTTP responses with status >= 400",
            "thresholds": {"yellow": 5, "red": 15},
        },
        {
            "title": "HTTP Response Time (ms)",
            "base_search": (
                'index={index} {host_filter} sourcetype=access_combined '
                '| stats avg(response_time_ms) as avg_response_time by host'
            ),
            "metric": "avg_response_time",
            "unit": "ms",
            "aggregate_statop": "avg",
            "description": "Average HTTP response time",
            "thresholds": {"yellow": 2000, "red": 5000},
        },
        {
            "title": "Requests Per Second",
            "base_search": (
                'index={index} {host_filter} sourcetype=access_combined '
                '| bucket span=1m _time '
                '| stats count as requests by _time, host '
                '| eval rps=requests/60'
            ),
            "metric": "rps",
            "unit": "req/s",
            "aggregate_statop": "avg",
            "description": "HTTP requests per second",
            "thresholds": {"yellow": None, "red": None},
        },
    ],

    # ── Application server ─────────────────────────────────────────────────
    "app_server": [
        {
            "title": "Application Error Rate (%)",
            "base_search": (
                'index={index} {host_filter} (log_level=ERROR OR log_level=FATAL OR severity=error) '
                '| stats count as errors by host '
                '| appendcols [search index={index} {host_filter} | stats count as total by host] '
                '| eval error_pct=round(errors/total*100,2)'
            ),
            "metric": "error_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 1, "red": 5},
        },
        {
            "title": "JVM Heap Utilization (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=jvm_metrics metric_name=heap_used_pct '
                '| stats avg(metric_value) as heap_pct by host'
            ),
            "metric": "heap_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 75, "red": 90},
        },
        {
            "title": "Thread Pool Queue Depth",
            "base_search": (
                'index={index} {host_filter} metric_name=thread_pool_queue_size '
                '| stats avg(metric_value) as queue_depth by host'
            ),
            "metric": "queue_depth",
            "unit": "threads",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 50, "red": 200},
        },
    ],

    # ── Database ───────────────────────────────────────────────────────────
    "database": [
        {
            "title": "Query Latency (ms)",
            "base_search": (
                'index={index} {host_filter} sourcetype=db_audit '
                '| stats avg(duration_ms) as avg_query_latency by host'
            ),
            "metric": "avg_query_latency",
            "unit": "ms",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 500, "red": 2000},
        },
        {
            "title": "Active Connections",
            "base_search": (
                'index={index} {host_filter} metric_name=db_connections_active '
                '| stats avg(metric_value) as active_conns by host'
            ),
            "metric": "active_conns",
            "unit": "connections",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 80, "red": 100},
        },
        {
            "title": "Replication Lag (seconds)",
            "base_search": (
                'index={index} {host_filter} metric_name=replication_lag_seconds '
                '| stats max(metric_value) as replication_lag by host'
            ),
            "metric": "replication_lag",
            "unit": "seconds",
            "aggregate_statop": "max",
            "thresholds": {"yellow": 10, "red": 60},
        },
        {
            "title": "Failed Transactions (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=db_audit '
                '| eval failed=if(status="failed" OR status="error",1,0) '
                '| stats count as total, sum(failed) as failures by host '
                '| eval failure_pct=round(failures/total*100,2)'
            ),
            "metric": "failure_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 1, "red": 5},
        },
    ],

    # ── Infrastructure / OS ────────────────────────────────────────────────
    "linux_host": [
        {
            "title": "CPU Utilization (%)",
            "base_search": (
                'index={index} {host_filter} metric_name=cpu.user '
                '| stats avg(metric_value) as cpu_pct by host'
            ),
            "metric": "cpu_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 70, "red": 90},
        },
        {
            "title": "Memory Utilization (%)",
            "base_search": (
                'index={index} {host_filter} metric_name=memory.utilization '
                '| stats avg(metric_value) as mem_pct by host'
            ),
            "metric": "mem_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 80, "red": 95},
        },
        {
            "title": "Disk Utilization (%)",
            "base_search": (
                'index={index} {host_filter} metric_name=disk.utilization '
                '| stats max(metric_value) as disk_pct by host'
            ),
            "metric": "disk_pct",
            "unit": "%",
            "aggregate_statop": "max",
            "thresholds": {"yellow": 80, "red": 95},
        },
    ],

    # ── Kubernetes ─────────────────────────────────────────────────────────
    "kubernetes": [
        {
            "title": "Pod Restart Rate",
            "base_search": (
                'index={index} {host_filter} sourcetype=kube:events reason=BackOff OR reason=CrashLoopBackOff '
                '| stats count as restarts by namespace'
            ),
            "metric": "restarts",
            "unit": "restarts/5m",
            "aggregate_statop": "sum",
            "thresholds": {"yellow": 3, "red": 10},
        },
        {
            "title": "Pod Availability (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=kube:pods '
                '| eval available=if(status="Running",1,0) '
                '| stats count as total, sum(available) as running by namespace '
                '| eval availability_pct=round(running/total*100,2)'
            ),
            "metric": "availability_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 95, "red": 90},
        },
        {
            "title": "Container CPU Throttling (%)",
            "base_search": (
                'index={index} {host_filter} metric_name=kube.container.cpu.throttling_data.throttled_time '
                '| stats avg(metric_value) as throttle_pct by namespace'
            ),
            "metric": "throttle_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 20, "red": 50},
        },
    ],

    # ── Message queue / Kafka ──────────────────────────────────────────────
    "message_queue": [
        {
            "title": "Consumer Lag",
            "base_search": (
                'index={index} {host_filter} metric_name=kafka.consumer.lag '
                '| stats max(metric_value) as consumer_lag by consumer_group'
            ),
            "metric": "consumer_lag",
            "unit": "messages",
            "aggregate_statop": "max",
            "thresholds": {"yellow": 1000, "red": 10000},
        },
        {
            "title": "Messages In Per Second",
            "base_search": (
                'index={index} {host_filter} metric_name=kafka.server.BrokerTopicMetrics.MessagesInPerSec.OneMinuteRate '
                '| stats avg(metric_value) as msg_rate by broker'
            ),
            "metric": "msg_rate",
            "unit": "msg/s",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": None, "red": None},
        },
    ],

    # ── API Gateway ────────────────────────────────────────────────────────
    "api_gateway": [
        {
            "title": "API Error Rate (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=api_gateway '
                '| eval error=if(status_code>=400,1,0) '
                '| stats count as total, sum(error) as errors by api_name '
                '| eval error_pct=round(errors/total*100,2)'
            ),
            "metric": "error_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 1, "red": 5},
        },
        {
            "title": "API Latency P95 (ms)",
            "base_search": (
                'index={index} {host_filter} sourcetype=api_gateway '
                '| stats p95(latency_ms) as p95_latency by api_name'
            ),
            "metric": "p95_latency",
            "unit": "ms",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 1000, "red": 3000},
        },
        {
            "title": "Rate Limit Hits",
            "base_search": (
                'index={index} {host_filter} sourcetype=api_gateway status_code=429 '
                '| stats count as rate_limit_hits by api_name'
            ),
            "metric": "rate_limit_hits",
            "unit": "hits/5m",
            "aggregate_statop": "sum",
            "thresholds": {"yellow": 10, "red": 100},
        },
    ],

    # ── Payment processing (FSI) ───────────────────────────────────────────
    "payment_processor": [
        {
            "title": "Transaction Decline Rate (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=payment_transactions '
                '| eval declined=if(status="DECLINED",1,0) '
                '| stats count as total, sum(declined) as declines by payment_method '
                '| eval decline_pct=round(declines/total*100,2)'
            ),
            "metric": "decline_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 2, "red": 10},
        },
        {
            "title": "Payment Processing Latency (ms)",
            "base_search": (
                'index={index} {host_filter} sourcetype=payment_transactions '
                '| stats avg(processing_time_ms) as avg_latency by payment_method'
            ),
            "metric": "avg_latency",
            "unit": "ms",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 2000, "red": 5000},
        },
        {
            "title": "Failed Settlements",
            "base_search": (
                'index={index} {host_filter} sourcetype=payment_settlements status=FAILED '
                '| stats count as failed_settlements'
            ),
            "metric": "failed_settlements",
            "unit": "count",
            "aggregate_statop": "sum",
            "thresholds": {"yellow": 1, "red": 5},
        },
    ],

    # ── Fraud detection ────────────────────────────────────────────────────
    "fraud_detection": [
        {
            "title": "Fraud Score Above Threshold Rate (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=fraud_scores '
                '| eval flagged=if(fraud_score>=0.7,1,0) '
                '| stats count as total, sum(flagged) as flagged_count '
                '| eval flagged_pct=round(flagged_count/total*100,2)'
            ),
            "metric": "flagged_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 1, "red": 5},
        },
        {
            "title": "Model Inference Latency (ms)",
            "base_search": (
                'index={index} {host_filter} sourcetype=fraud_scores '
                '| stats avg(inference_ms) as avg_inference_latency'
            ),
            "metric": "avg_inference_latency",
            "unit": "ms",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 100, "red": 500},
        },
    ],

    # ── Identity / Auth ────────────────────────────────────────────────────
    "auth_service": [
        {
            "title": "Authentication Failure Rate (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=auth_logs '
                '| eval failed=if(action="failure",1,0) '
                '| stats count as total, sum(failed) as failures by app '
                '| eval failure_pct=round(failures/total*100,2)'
            ),
            "metric": "failure_pct",
            "unit": "%",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": 5, "red": 20},
        },
        {
            "title": "MFA Challenge Rate (%)",
            "base_search": (
                'index={index} {host_filter} sourcetype=auth_logs action=mfa_challenge '
                '| stats count as mfa_challenges by hour'
            ),
            "metric": "mfa_challenges",
            "unit": "challenges/hr",
            "aggregate_statop": "avg",
            "thresholds": {"yellow": None, "red": None},
        },
    ],
}

# Aliases so SNOW CI classes map to template keys
CI_CLASS_ALIASES: dict[str, str] = {
    # ServiceNow CI class -> template key
    "cmdb_ci_web_server": "web_server",
    "cmdb_ci_app_server": "app_server",
    "cmdb_ci_database": "database",
    "cmdb_ci_db_instance": "database",
    "cmdb_ci_linux_server": "linux_host",
    "cmdb_ci_unix_server": "linux_host",
    "cmdb_ci_win_server": "linux_host",
    "cmdb_ci_k8s_cluster": "kubernetes",
    "cmdb_ci_k8s_namespace": "kubernetes",
    "cmdb_ci_mq_server": "message_queue",
    "cmdb_ci_apigee": "api_gateway",
    "cmdb_ci_service": "web_server",   # generic fallback
    # semantic shortcuts
    "web": "web_server",
    "app": "app_server",
    "db": "database",
    "k8s": "kubernetes",
    "kafka": "message_queue",
    "api": "api_gateway",
    "payment": "payment_processor",
    "fraud": "fraud_detection",
    "auth": "auth_service",
}


def get_kpis_for_service_type(service_type: str) -> list[dict]:
    """Return KPI template dicts for a given service type or CI class."""
    key = CI_CLASS_ALIASES.get(service_type.lower(), service_type.lower())
    return KPI_TEMPLATES.get(key, KPI_TEMPLATES.get("web_server", []))


def render_kpi(kpi_template: dict, index: str = "main", host_filter: str = "") -> dict:
    """Substitute {index} and {host_filter} in SPL template."""
    host_part = f"host={host_filter}" if host_filter else ""
    rendered = dict(kpi_template)
    rendered["base_search"] = (
        kpi_template["base_search"]
        .replace("{index}", index)
        .replace("{host_filter}", host_part)
        .strip()
    )
    return rendered
