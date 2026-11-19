"""
Pre-flight data readiness checker.

Connects to a Splunk REST API and checks whether the indexed data
is sufficient for a successful ITSI onboarding.

Checks performed:
  1. Connectivity and auth
  2. Required indexes present
  3. Metric data available (em_metrics / itsi_im_metrics)
  4. Host entities discoverable
  5. Time coverage (data freshness)
  6. Recommended sourcetypes present
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


REQUIRED_METRIC_INDEXES = ["em_metrics", "itsi_im_metrics", "metrics", "perf"]
RECOMMENDED_SOURCETYPES = [
    "access_combined", "access_combined_wcookie",   # web
    "log4j", "java_app", "app_log",                 # app
    "mysql", "mssql", "postgres", "oracle",         # db
    "cpu", "vmstat", "iostat",                      # host
    "kube:events", "kube:pods",                     # k8s
]


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    detail: Any = None


@dataclass
class PreflightReport:
    splunk_url: str
    checks: list[CheckResult] = field(default_factory=list)
    indexes_found: list[str] = field(default_factory=list)
    sourcetypes_found: list[str] = field(default_factory=list)
    host_count: int = 0
    earliest_data: str = ""
    latest_data: str = ""

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def score(self) -> int:
        if not self.checks:
            return 0
        return round(sum(1 for c in self.checks if c.passed) / len(self.checks) * 100)

    def summary(self) -> str:
        lines = [
            f"Pre-flight Report: {self.splunk_url}",
            f"Overall Score: {self.score}% ({sum(1 for c in self.checks if c.passed)}/{len(self.checks)} checks passed)",
            "",
        ]
        for c in self.checks:
            icon = "✓" if c.passed else "✗"
            lines.append(f"  {icon} {c.name}: {c.message}")
        lines += [
            "",
            f"Indexes found: {', '.join(self.indexes_found) or 'none'}",
            f"Sourcetypes: {', '.join(self.sourcetypes_found[:10]) or 'none'}",
            f"Discoverable hosts: {self.host_count}",
        ]
        if self.earliest_data:
            lines.append(f"Data range: {self.earliest_data} → {self.latest_data}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "splunk_url": self.splunk_url,
            "score": self.score,
            "passed": self.passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "message": c.message}
                for c in self.checks
            ],
            "indexes_found": self.indexes_found,
            "sourcetypes_found": self.sourcetypes_found,
            "host_count": self.host_count,
            "data_range": {"earliest": self.earliest_data, "latest": self.latest_data},
        }


class PreflightChecker:
    def __init__(self, url: str, token: str, verify_ssl: bool = False):
        self.base = url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _search(self, spl: str, earliest: str = "-24h", latest: str = "now") -> list[dict]:
        """Run a one-shot search and return results."""
        resp = self.session.post(
            f"{self.base}/services/search/jobs/export",
            data={
                "search": f"search {spl}",
                "output_mode": "json",
                "earliest_time": earliest,
                "latest_time": latest,
                "count": 100,
            },
            timeout=30,
        )
        resp.raise_for_status()
        results = []
        for line in resp.text.strip().splitlines():
            try:
                obj = json.loads(line)
                if obj.get("result"):
                    results.append(obj["result"])
            except json.JSONDecodeError:
                pass
        return results

    def check_connectivity(self) -> CheckResult:
        try:
            resp = self.session.get(f"{self.base}/services/server/info", timeout=10)
            resp.raise_for_status()
            info = resp.json()
            version = info.get("entry", [{}])[0].get("content", {}).get("version", "unknown")
            return CheckResult("connectivity", True, f"Connected — Splunk {version}")
        except Exception as e:
            return CheckResult("connectivity", False, f"Cannot connect: {e}")

    def check_indexes(self, report: PreflightReport) -> CheckResult:
        try:
            resp = self.session.get(
                f"{self.base}/services/data/indexes",
                params={"output_mode": "json", "count": 200},
                timeout=15,
            )
            resp.raise_for_status()
            entries = resp.json().get("entry", [])
            names = [e["name"] for e in entries]
            report.indexes_found = names
            has_metrics = any(n in names for n in REQUIRED_METRIC_INDEXES)
            if has_metrics:
                return CheckResult("metric_indexes", True, f"Metric index found in: {names}")
            return CheckResult("metric_indexes", False,
                               f"No metric indexes found. Expected one of: {REQUIRED_METRIC_INDEXES}. "
                               "Install Splunk Infrastructure Monitoring Add-on or configure metrics collection.")
        except Exception as e:
            return CheckResult("metric_indexes", False, f"Could not list indexes: {e}")

    def check_host_entities(self, report: PreflightReport) -> CheckResult:
        try:
            results = self._search(
                "index=* metric_name=cpu* OR metric_name=memory* "
                "| stats dc(host) as host_count"
            )
            count = int(results[0].get("host_count", 0)) if results else 0
            report.host_count = count
            if count > 0:
                return CheckResult("host_entities", True, f"{count} hosts found with metric data")
            return CheckResult("host_entities", False,
                               "No hosts found with metric data. Configure the Splunk Add-on for Infrastructure "
                               "or Universal Forwarder with system metrics.")
        except Exception as e:
            return CheckResult("host_entities", False, f"Host check failed: {e}")

    def check_sourcetypes(self, report: PreflightReport) -> CheckResult:
        try:
            results = self._search(
                "index=* | stats count by sourcetype | sort -count"
            )
            found = [r.get("sourcetype", "") for r in results[:20]]
            report.sourcetypes_found = found
            matched = [st for st in found if st in RECOMMENDED_SOURCETYPES]
            if matched:
                return CheckResult("sourcetypes", True, f"Recognized: {', '.join(matched[:5])}")
            return CheckResult("sourcetypes", False,
                               f"No recognized ITSI sourcetypes. Found: {', '.join(found[:5])}. "
                               "Consider adding content packs for your tech stack.")
        except Exception as e:
            return CheckResult("sourcetypes", False, f"Sourcetype check failed: {e}")

    def check_data_freshness(self, report: PreflightReport) -> CheckResult:
        try:
            results = self._search(
                "index=* | stats min(_time) as earliest, max(_time) as latest"
            )
            if results:
                report.earliest_data = results[0].get("earliest", "")
                report.latest_data = results[0].get("latest", "")
                return CheckResult("data_freshness", True,
                                   f"Data present: {report.earliest_data} → {report.latest_data}")
            return CheckResult("data_freshness", False, "No data found in any index")
        except Exception as e:
            return CheckResult("data_freshness", False, f"Freshness check failed: {e}")

    def run(self) -> PreflightReport:
        report = PreflightReport(splunk_url=self.base)

        conn = self.check_connectivity()
        report.checks.append(conn)
        if not conn.passed:
            return report

        report.checks.append(self.check_indexes(report))
        report.checks.append(self.check_host_entities(report))
        report.checks.append(self.check_sourcetypes(report))
        report.checks.append(self.check_data_freshness(report))
        return report
