"""
ITSI demo readiness probe.

Checks whether a live ITSI instance is ready to demo against a given content pack:
  1. Connectivity + auth
  2. All pack services exist in ITSI
  3. Services have active health scores (data flowing)
  4. KPIs have aggregate values (itsi_summary index)
  5. Entities are present and matched
  6. Correlation searches exist and are enabled
  7. KPI backfill jobs complete
  8. Active degrade scenario status (from local state file)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Local state file written by degrade executor
SCENARIO_STATE_FILE = Path.home() / ".itsi_accelerator_state.json"

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"


@dataclass
class ProbeCheck:
    name: str
    status: str          # pass | warn | fail | skip
    message: str
    detail: str = ""

    @property
    def icon(self) -> str:
        return {"pass": "✓", "warn": "!", "fail": "✗", "skip": "·"}[self.status]

    @property
    def color(self) -> str:
        return {"pass": "green", "warn": "yellow", "fail": "red", "skip": "dim"}[self.status]


@dataclass
class ProbeReport:
    checks: list[ProbeCheck] = field(default_factory=list)
    checked_at: float = field(default_factory=time.time)

    @property
    def ready(self) -> bool:
        return not any(c.status == STATUS_FAIL for c in self.checks)

    @property
    def verdict(self) -> str:
        if any(c.status == STATUS_FAIL for c in self.checks):
            return "NOT READY"
        if any(c.status == STATUS_WARN for c in self.checks):
            return "CAUTION"
        return "READY"

    @property
    def verdict_color(self) -> str:
        return {"NOT READY": "red", "CAUTION": "yellow", "READY": "green"}[self.verdict]

    @property
    def score(self) -> int:
        countable = [c for c in self.checks if c.status != STATUS_SKIP]
        if not countable:
            return 0
        passed = sum(1 for c in countable if c.status == STATUS_PASS)
        return round(passed / len(countable) * 100)

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "score": self.score,
            "checked_at": self.checked_at,
            "checks": [
                {"name": c.name, "status": c.status, "message": c.message, "detail": c.detail}
                for c in self.checks
            ],
        }


class ProbeChecker:
    """
    Checks ITSI demo readiness against a live Splunk/ITSI instance.

    Args:
        url: Splunk base URL, e.g. https://my-show.splunkcloud.com
        token: Splunk auth token (Bearer)
        pack_dict: Content pack dict (from JSON file) — used to cross-reference service names
        verify_ssl: Whether to verify SSL certificates
    """

    def __init__(self, url: str, token: str, pack_dict: dict | None = None, verify_ssl: bool = False):
        self.base = url.rstrip("/")
        self.pack_dict = pack_dict or {}
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        # Service titles from the pack for cross-referencing
        self._pack_titles: set[str] = {
            s["title"]
            for s in self.pack_dict.get("data", {}).get("services", [])
        }

    def _get(self, path: str, params: dict | None = None) -> tuple[bool, Any]:
        """GET with graceful error handling. Returns (ok, body_or_error_string)."""
        try:
            resp = self.session.get(
                f"{self.base}{path}",
                params={"output_mode": "json", "count": 200, **(params or {})},
                timeout=15,
            )
            resp.raise_for_status()
            return True, resp.json()
        except requests.HTTPError as e:
            return False, f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        except Exception as e:
            return False, str(e)

    def _search(self, spl: str, earliest: str = "-15m") -> list[dict]:
        """Run a one-shot search export and return result rows."""
        try:
            resp = self.session.post(
                f"{self.base}/services/search/jobs/export",
                data={
                    "search": f"search {spl}",
                    "output_mode": "json",
                    "earliest_time": earliest,
                    "latest_time": "now",
                    "count": 500,
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
        except Exception:
            return []

    # ── Individual checks ─────────────────────────────────────────────────────

    def check_connectivity(self) -> ProbeCheck:
        ok, body = self._get("/services/server/info")
        if not ok:
            return ProbeCheck("Connectivity", STATUS_FAIL, f"Cannot connect: {body}")
        version = (body.get("entry") or [{}])[0].get("content", {}).get("version", "unknown")
        return ProbeCheck("Connectivity", STATUS_PASS, f"Splunk {version}")

    def check_services_exist(self) -> ProbeCheck:
        if not self._pack_titles:
            return ProbeCheck("Services exist", STATUS_SKIP, "No pack loaded — skipping")

        ok, body = self._get("/servicesNS/nobody/SA-ITOA/itsi/service")
        if not ok:
            return ProbeCheck("Services exist", STATUS_FAIL, f"ITSI service API error: {body}")

        entries = body.get("entry", [])
        itsi_titles = {e.get("content", {}).get("title") or e.get("name", "") for e in entries}

        missing = self._pack_titles - itsi_titles
        found = len(self._pack_titles) - len(missing)

        if missing:
            return ProbeCheck(
                "Services exist",
                STATUS_FAIL if len(missing) > len(self._pack_titles) // 2 else STATUS_WARN,
                f"{found}/{len(self._pack_titles)} services found in ITSI",
                detail=f"Missing: {', '.join(sorted(missing)[:5])}{'...' if len(missing) > 5 else ''}",
            )
        return ProbeCheck("Services exist", STATUS_PASS, f"All {len(self._pack_titles)} services present")

    def check_health_scores(self) -> ProbeCheck:
        ok, body = self._get("/servicesNS/nobody/SA-ITOA/itsi/service")
        if not ok:
            return ProbeCheck("Health scores", STATUS_FAIL, f"API error: {body}")

        entries = body.get("entry", [])
        if not entries:
            return ProbeCheck("Health scores", STATUS_FAIL, "No services found in ITSI")

        # Filter to pack services only if we have a pack
        if self._pack_titles:
            entries = [e for e in entries
                       if (e.get("content", {}).get("title") or e.get("name", "")) in self._pack_titles]

        total = len(entries)
        with_score = sum(
            1 for e in entries
            if e.get("content", {}).get("health_score") not in (None, "", "N/A", 0)
        )

        if total == 0:
            return ProbeCheck("Health scores", STATUS_WARN, "No matching services found")
        if with_score == 0:
            return ProbeCheck("Health scores", STATUS_FAIL,
                              "No services have health scores — KPI data may not be flowing")
        if with_score < total:
            return ProbeCheck("Health scores", STATUS_WARN,
                              f"{with_score}/{total} services have health scores")
        return ProbeCheck("Health scores", STATUS_PASS, f"All {total} services have health scores")

    def check_kpi_data(self) -> ProbeCheck:
        results = self._search(
            "index=itsi_summary | stats dc(service_id) as svc_count, dc(kpi_id) as kpi_count",
            earliest="-15m",
        )
        if not results:
            return ProbeCheck("KPI data flow", STATUS_FAIL,
                              "No data in itsi_summary index (last 15m) — KPIs not computing")
        row = results[0]
        svc_count = int(row.get("svc_count", 0))
        kpi_count = int(row.get("kpi_count", 0))
        if kpi_count == 0:
            return ProbeCheck("KPI data flow", STATUS_FAIL, "itsi_summary index empty — no KPI computations")
        return ProbeCheck("KPI data flow", STATUS_PASS,
                          f"{kpi_count} KPIs computing across {svc_count} services (last 15m)")

    def check_entities(self) -> ProbeCheck:
        ok, body = self._get("/servicesNS/nobody/SA-ITOA/itsi/entity")
        if not ok:
            return ProbeCheck("Entities", STATUS_FAIL, f"Entity API error: {body}")

        entries = body.get("entry", [])
        total = len(entries)

        if total == 0:
            return ProbeCheck("Entities", STATUS_WARN,
                              "No entities in ITSI — services will have no entity breakdown")

        # Count how many entities link back to pack services
        linked = sum(
            1 for e in entries
            if any(
                s.get("title") in self._pack_titles or s.get("_key")
                for s in e.get("content", {}).get("services", [])
            )
        ) if self._pack_titles else total

        return ProbeCheck("Entities", STATUS_PASS, f"{total} entities ({linked} linked to pack services)")

    def check_correlation_searches(self) -> ProbeCheck:
        # Look for saved searches with the ITSI event generator action enabled
        ok, body = self._get(
            "/services/saved/searches",
            params={"search": "action.itsi_event_generator=1", "count": 200},
        )
        if not ok:
            return ProbeCheck("Correlation searches", STATUS_SKIP,
                              f"Could not query saved searches: {body}")

        entries = body.get("entry", [])
        if not entries:
            return ProbeCheck("Correlation searches", STATUS_WARN,
                              "No correlation searches found — episodes won't fire automatically")

        disabled = [e["name"] for e in entries if e.get("content", {}).get("disabled") in (1, "1", True)]
        enabled_count = len(entries) - len(disabled)

        if disabled:
            return ProbeCheck("Correlation searches", STATUS_WARN,
                              f"{enabled_count}/{len(entries)} enabled",
                              detail=f"Disabled: {', '.join(disabled[:3])}{'...' if len(disabled) > 3 else ''}")
        return ProbeCheck("Correlation searches", STATUS_PASS, f"{len(entries)} searches enabled")

    def check_backfill(self) -> ProbeCheck:
        ok, body = self._get("/servicesNS/nobody/SA-ITOA/itsi/backfill_chunk")
        if not ok:
            # Backfill endpoint may not exist on all ITSI versions — skip gracefully
            return ProbeCheck("KPI backfill", STATUS_SKIP, "Backfill API not available on this ITSI version")

        entries = body.get("entry", [])
        if not entries:
            return ProbeCheck("KPI backfill", STATUS_PASS, "No active backfill jobs")

        in_progress = [e for e in entries if e.get("content", {}).get("status") != "complete"]
        if in_progress:
            return ProbeCheck("KPI backfill", STATUS_WARN,
                              f"{len(in_progress)} backfill job(s) still running — KPI history may be incomplete")
        return ProbeCheck("KPI backfill", STATUS_PASS, f"{len(entries)} backfill job(s) complete")

    def check_active_scenario(self) -> ProbeCheck:
        if not SCENARIO_STATE_FILE.exists():
            return ProbeCheck("Active scenario", STATUS_PASS, "No active degrade scenario")

        try:
            state = json.loads(SCENARIO_STATE_FILE.read_text())
        except Exception:
            return ProbeCheck("Active scenario", STATUS_SKIP, "Could not read scenario state file")

        if not state.get("active"):
            return ProbeCheck("Active scenario", STATUS_PASS, "No active degrade scenario")

        name = state.get("scenario_name", "Unknown")
        recover_at = state.get("recover_at", 0)
        now = time.time()
        remaining = int(recover_at - now)

        if remaining > 0:
            mins, secs = divmod(remaining, 60)
            time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
            return ProbeCheck("Active scenario", STATUS_WARN,
                              f"ACTIVE: '{name}' — {time_str} until auto-recovery")
        else:
            overdue = int(now - recover_at)
            return ProbeCheck("Active scenario", STATUS_WARN,
                              f"ACTIVE: '{name}' — {overdue}s overdue for recovery (may need manual cleanup)")

    # ── Run all checks ────────────────────────────────────────────────────────

    def run(self) -> ProbeReport:
        report = ProbeReport()

        conn = self.check_connectivity()
        report.checks.append(conn)
        if conn.status == STATUS_FAIL:
            # Can't do anything without connectivity
            return report

        report.checks.append(self.check_services_exist())
        report.checks.append(self.check_health_scores())
        report.checks.append(self.check_kpi_data())
        report.checks.append(self.check_entities())
        report.checks.append(self.check_correlation_searches())
        report.checks.append(self.check_backfill())
        report.checks.append(self.check_active_scenario())

        return report
