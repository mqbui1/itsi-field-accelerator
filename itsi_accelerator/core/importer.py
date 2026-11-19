"""
ITSI REST API importer — pushes a generated content pack into live ITSI.

Endpoint reference:
  POST /servicesNS/nobody/SA-ITOA/itsi/content_packs/import
  POST /servicesNS/nobody/SA-ITOA/event_management_interface/notable_event_aggregation_policy
  POST /servicesNS/nobody/SA-ITOA/itoa_interface/service  (direct service create)

For demos/field use, the content pack import endpoint is preferred since it handles
dependency ordering (base searches -> threshold templates -> services).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from itsi_accelerator.core.models import ContentPack


@dataclass
class ImportResult:
    success: bool
    services_created: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ITSIImporter:
    def __init__(self, url: str, token: str, verify_ssl: bool = False):
        self.base = url.rstrip("/")
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })

    def _post(self, path: str, payload: dict) -> dict:
        resp = self.session.post(
            f"{self.base}{path}",
            data=json.dumps(payload),
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()

    def import_pack(self, pack: ContentPack) -> ImportResult:
        """Import a full content pack via ITSI's content pack import endpoint."""
        pack_dict = pack.to_dict()
        errors = []
        created = 0

        # Import via content pack endpoint
        try:
            result = self._post(
                "/servicesNS/nobody/SA-ITOA/itsi/content_packs/import",
                {"content_pack": pack_dict, "overwrite": False},
            )
            created = len(pack.services)
        except requests.HTTPError as e:
            errors.append(f"Content pack import failed: {e.response.text}")
            # Fall back: create services one-by-one
            created, errs = self._import_services_direct(pack)
            errors.extend(errs)

        return ImportResult(success=len(errors) == 0, services_created=created, errors=errors)

    def _import_services_direct(self, pack: ContentPack) -> tuple[int, list[str]]:
        """Fallback: create services individually via itoa_interface."""
        created = 0
        errors = []
        for svc in pack.services:
            try:
                self._post(
                    "/servicesNS/nobody/SA-ITOA/itoa_interface/service",
                    svc.to_dict(),
                )
                created += 1
            except requests.HTTPError as e:
                errors.append(f"Failed to create service '{svc.title}': {e.response.text[:200]}")
        return created, errors

    def test_connection(self) -> bool:
        try:
            resp = self.session.get(
                f"{self.base}/servicesNS/nobody/SA-ITOA/itoa_interface/service",
                params={"output_mode": "json", "count": 1},
                timeout=10,
            )
            resp.raise_for_status()
            return True
        except Exception:
            return False
