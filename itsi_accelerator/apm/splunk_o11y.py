"""
Splunk Observability Cloud APM client.

Fetches the live service map (nodes + edges) from the O11y APM REST API
and returns it in a normalized format for downstream ITSI classification.

API endpoint:
  GET https://api.<realm>.signalfx.com/v2/apm/v1/service-map
  Headers: X-SF-TOKEN: <token>
  Params:  sf_environment, startTimeMs, endTimeMs
"""

from __future__ import annotations

import time
from typing import Any

import requests


class SplunkO11yClient:
    """Minimal Splunk O11y APM REST client."""

    def __init__(self, realm: str, token: str, verify_ssl: bool = True):
        self.base_url = f"https://api.{realm}.signalfx.com"
        self.session = requests.Session()
        self.session.headers.update({
            "X-SF-TOKEN": token,
            "Content-Type": "application/json",
        })
        self.session.verify = verify_ssl

    def get_service_map(
        self,
        environment: str,
        lookback_minutes: int = 60,
    ) -> dict[str, Any]:
        """
        Fetch the APM service map for a given environment.

        Returns:
            {
                "nodes": [{"name": str, "environment": str, ...}, ...],
                "edges": [{"origin": str, "destination": str, ...}, ...],
            }

        Raises:
            requests.HTTPError: on 4xx/5xx responses
            RuntimeError: if the response shape is unexpected
        """
        now_ms = int(time.time() * 1000)
        start_ms = now_ms - lookback_minutes * 60 * 1000

        resp = self.session.get(
            f"{self.base_url}/v2/apm/v1/service-map",
            params={
                "sf_environment": environment,
                "startTimeMs": start_ms,
                "endTimeMs": now_ms,
            },
            timeout=30,
        )
        resp.raise_for_status()

        body = resp.json()
        # Response is either {"data": {"nodes": [...], "edges": [...]}} or the inner dict directly
        if "data" in body and isinstance(body["data"], dict):
            inner = body["data"]
        else:
            inner = body

        nodes = inner.get("nodes") or inner.get("services") or []
        edges = inner.get("edges") or inner.get("dependencies") or []

        if not nodes:
            raise RuntimeError(
                f"No services found for environment '{environment}' in the last {lookback_minutes} minutes. "
                "Verify the environment name and that APM data is flowing to this org."
            )

        return {"nodes": nodes, "edges": edges}
