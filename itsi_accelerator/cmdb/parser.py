"""
CMDB parser — converts a ServiceNow CMDB export to an ITSI service tree.

Supported input formats:
  - CSV export from SNOW CI Relationships table (cmdb_rel_ci)
  - JSON export with 'cis' and 'relationships' arrays
  - Flat CSV of CIs (name, ci_class, business_service, parent_ci)

Expected CSV columns (auto-detected):
  name / sys_name       - CI display name
  sys_class_name        - CI class (e.g. cmdb_ci_web_server)
  parent                - parent CI name or sys_id
  business_service      - top-level business service
  environment           - prod/staging/dev
  short_description     - optional description
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from itsi_accelerator.core.models import ContentPack, EntityRule, KPI, Service, new_id
from itsi_accelerator.templates.kpi_library import get_kpis_for_service_type, render_kpi


# Column name normalization
_COL_ALIASES = {
    "name": "name",
    "sys_name": "name",
    "ci_name": "name",
    "display_name": "name",
    "sys_class_name": "ci_class",
    "class": "ci_class",
    "ci_class": "ci_class",
    "type": "ci_class",
    "parent": "parent",
    "parent_ci": "parent",
    "parent_name": "parent",
    "u_parent": "parent",
    "business_service": "business_service",
    "business_service_name": "business_service",
    "biz_service": "business_service",
    "environment": "environment",
    "env": "environment",
    "short_description": "description",
    "description": "description",
    "u_environment": "environment",
}


def _normalize_columns(row: dict) -> dict:
    return {_COL_ALIASES.get(k.lower().strip(), k.lower().strip()): v for k, v in row.items()}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", text.lower().strip())


class CMDBParser:
    def __init__(self, index: str = "main", default_env: str = "production"):
        self.index = index
        self.default_env = default_env

    def parse_csv(self, path: str | Path) -> list[dict]:
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(_normalize_columns(row))
        return rows

    def parse_json(self, path: str | Path) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # Support {cis: [...]} or flat list
        if isinstance(data, list):
            return [_normalize_columns(r) for r in data]
        if "cis" in data:
            return [_normalize_columns(r) for r in data["cis"]]
        if "result" in data:
            return [_normalize_columns(r) for r in data["result"]]
        return [_normalize_columns(r) for r in data.get("records", [])]

    def parse(self, path: str | Path) -> list[dict]:
        p = Path(path)
        if p.suffix.lower() == ".json":
            return self.parse_json(p)
        return self.parse_csv(p)

    def build_content_pack(self, rows: list[dict], pack_title: str = "CMDB Import") -> ContentPack:
        pack = ContentPack(
            title=pack_title,
            description=f"Auto-generated from CMDB export. {len(rows)} CIs processed.",
        )

        # Build a name->row index
        ci_map: dict[str, dict] = {}
        for row in rows:
            name = row.get("name", "").strip()
            if name:
                ci_map[name] = row

        # Group by business_service -> parent -> children
        biz_services: dict[str, list[dict]] = {}
        for row in rows:
            biz = row.get("business_service", "").strip() or "Uncategorized"
            biz_services.setdefault(biz, []).append(row)

        created_service_keys: dict[str, str] = {}  # ci_name -> _key

        for biz_name, cis in biz_services.items():
            # Create the top-level business service
            biz_key = new_id()
            biz_svc = Service(
                title=biz_name,
                description=f"Business service: {biz_name}",
                _key=biz_key,
                tags=["field-accelerator", "business-service"],
            )
            pack.add_service(biz_svc)
            created_service_keys[biz_name] = biz_key

            # Build child services from CIs
            # First pass: create all services
            for row in cis:
                ci_name = row.get("name", "").strip()
                if not ci_name or ci_name == biz_name:
                    continue

                ci_class = row.get("ci_class", "").strip() or "web_server"
                description = row.get("description", "").strip()
                environment = row.get("environment", self.default_env).strip()

                svc = Service(
                    title=ci_name,
                    description=description or f"{ci_name} ({ci_class})",
                    tags=["field-accelerator", _slugify(ci_class), environment],
                )
                # Add entity rule matching by host name
                svc.entity_rules.append(
                    EntityRule(field="host", value=ci_name, rule_type="matches")
                )

                # Add KPIs from template library
                kpi_templates = get_kpis_for_service_type(ci_class)
                for tmpl in kpi_templates:
                    rendered = render_kpi(tmpl, index=self.index)
                    kpi = KPI(
                        title=rendered["title"],
                        base_search=rendered["base_search"],
                        unit=rendered.get("unit", ""),
                        aggregate_statop=rendered.get("aggregate_statop", "avg"),
                        description=rendered.get("description", ""),
                    )
                    svc.add_kpi(kpi)

                pack.add_service(svc)
                created_service_keys[ci_name] = svc._key

            # Second pass: wire up dependencies
            for row in cis:
                ci_name = row.get("name", "").strip()
                parent_name = row.get("parent", "").strip()
                if not ci_name:
                    continue

                svc_key = created_service_keys.get(ci_name)
                if svc_key is None:
                    continue

                # Find the actual service object
                svc_obj = next((s for s in pack.services if s._key == svc_key), None)
                if svc_obj is None:
                    continue

                if parent_name and parent_name in created_service_keys:
                    parent_key = created_service_keys[parent_name]
                else:
                    # Default parent is the business service
                    parent_key = biz_key

                parent_obj = next((s for s in pack.services if s._key == parent_key), None)
                if parent_obj and svc_key not in parent_obj.services_depends_on:
                    parent_obj.services_depends_on.append(svc_key)

        return pack


def build_pack_from_cmdb(
    input_path: str,
    pack_title: str = "CMDB Import",
    index: str = "main",
) -> ContentPack:
    """High-level convenience function."""
    parser = CMDBParser(index=index)
    rows = parser.parse(input_path)
    return parser.build_content_pack(rows, pack_title=pack_title)
