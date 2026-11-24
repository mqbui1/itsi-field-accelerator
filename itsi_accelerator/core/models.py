"""Core data models for ITSI objects (content pack schema)."""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4()).replace("-", "")


@dataclass
class KPIThresholdTemplate:
    title: str
    thresholds: dict[str, Any]
    _key: str = field(default_factory=new_id)
    object_type: str = "kpi_threshold_template"


@dataclass
class KPIBaseSearch:
    title: str
    base_search: str
    metric_qualifier: str
    entity_id_fields: str
    _key: str = field(default_factory=new_id)
    object_type: str = "kpi_base_search"


@dataclass
class KPI:
    title: str
    base_search: str            # SPL or base_search reference
    unit: str = ""
    aggregate_statop: str = "avg"
    entity_statop: str = "avg"
    threshold_template_id: str = ""
    description: str = ""
    _key: str = field(default_factory=new_id)
    object_type: str = "kpi"
    base_search_id: str = ""
    base_search_metric: str = ""
    kpi_base_search: str = ""
    search_type: str = "search"   # "search" | "base_search"
    alert_period: int = 5
    alert_lag: int = 30
    is_enabled: int = 1

    def to_dict(self) -> dict:
        return {
            "_key": self._key,
            "title": self.title,
            "type": self.search_type,
            "base_search": self.base_search,
            "base_search_id": self.base_search_id,
            "base_search_metric": self.base_search_metric,
            "kpi_base_search": self.kpi_base_search,
            "unit": self.unit,
            "aggregate_statop": self.aggregate_statop,
            "entity_statop": self.entity_statop,
            "threshold_template_id": self.threshold_template_id,
            "description": self.description,
            "alert_period": self.alert_period,
            "alert_lag": self.alert_lag,
            "is_enabled": self.is_enabled,
        }


@dataclass
class EntityRule:
    field: str
    value: str
    rule_type: str = "matches"  # "matches" | "contains" | "regex"


@dataclass
class Service:
    title: str
    description: str = ""
    kpis: list[KPI] = field(default_factory=list)
    entity_rules: list[EntityRule] = field(default_factory=list)
    services_depends_on: list[str] = field(default_factory=list)  # list of _key
    tags: list[str] = field(default_factory=list)
    _key: str = field(default_factory=new_id)
    object_type: str = "service"
    enabled: int = 1
    team: str = "Global"

    def add_kpi(self, kpi: KPI) -> None:
        self.kpis.append(kpi)

    def to_dict(self) -> dict:
        d = {
            "_key": self._key,
            "title": self.title,
            "description": self.description,
            "enabled": self.enabled,
            "object_type": self.object_type,
            "kpis": [k.to_dict() for k in self.kpis],
            "entity_rules": [
                {"field": r.field, "value": r.value, "rule_type": r.rule_type}
                for r in self.entity_rules
            ],
            "services_depends_on": self.services_depends_on,
            "tags": self.tags,
            "teams": [{"_key": self.team}],
        }
        # Always include the mandatory service health KPI
        if not any(k.title == "ServiceHealthScore" for k in self.kpis):
            d["kpis"].insert(0, {
                "_key": new_id(),
                "title": "ServiceHealthScore",
                "type": "service_health",
                "base_search": "",
                "threshold_template_id": "",
                "is_enabled": 1,
                "alert_period": 5,
                "alert_lag": 30,
            })
        return d


@dataclass
class Entity:
    title: str
    identifier_fields: list[str]        # fields that uniquely ID this entity (e.g. ["host"])
    informational_fields: list[dict]    # extra fields to show in entity detail view
    service_key: str = ""               # _key of the owning service
    _key: str = field(default_factory=new_id)
    object_type: str = "entity"

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "_key": self._key,
            "title": self.title,
            "object_type": self.object_type,
            "identifier": {
                "fields": self.identifier_fields,
                "values": ["*"],
            },
            "informational": self.informational_fields,
        }
        if self.service_key:
            d["services"] = [{"_key": self.service_key}]
        return d


@dataclass
class CorrelationSearch:
    name: str
    description: str
    search: str                     # SPL
    service_key: str = ""
    severity: str = "medium"        # low, medium, high, critical
    alert_title: str = ""
    cron_schedule: str = "*/5 * * * *"
    _key: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "_key": self._key,
            "name": self.name,
            "description": self.description,
            "search": self.search,
            "cron_schedule": self.cron_schedule,
            "disabled": 0,
            "alert.severity": self.severity,
            "is_notable": 1,
            "action.itsi_event_generator": "1",
            "action.itsi_event_generator.param.title": self.alert_title or self.name,
            "action.itsi_event_generator.param.severity": self.severity,
            "services": [{"_key": self.service_key}] if self.service_key else [],
        }


@dataclass
class NotableEventAggregationPolicy:
    title: str
    description: str
    service_key: str
    break_after_silence_minutes: int = 15
    split_by_field: str = "service_id"
    _key: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return {
            "_key": self._key,
            "title": self.title,
            "description": self.description,
            "run_time_based_auto_pause": 1,
            "auto_pause_after_trigger_time": self.break_after_silence_minutes * 60,
            "notable_event_count_enabled": 1,
            "rules": [
                {
                    "title": f"Group by {self.split_by_field}",
                    "type": "auto",
                    "filter_criteria": {
                        "clause": "and",
                        "items": [
                            {"field": "service_id", "value": self.service_key, "operator": "="}
                        ],
                    },
                    "break_criteria": {
                        "clause": "or",
                        "items": [
                            {"field": "break_by_nb_of_events", "value": "100"},
                        ],
                    },
                    "split_by_field": self.split_by_field,
                }
            ],
            "executing_actions": [
                {
                    "type": "itsi_event_action_link_url",
                    "execute_on": "trigger",
                    "params": {"label": "Investigate in ITSI", "url": ""},
                }
            ],
        }


@dataclass
class ContentPack:
    title: str
    description: str = ""
    version: str = "1.0.0"
    _key: str = field(default_factory=new_id)
    services: list[Service] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    kpi_base_searches: list[KPIBaseSearch] = field(default_factory=list)
    threshold_templates: list[KPIThresholdTemplate] = field(default_factory=list)
    # These are exported separately (not part of content pack import API)
    correlation_searches: list[CorrelationSearch] = field(default_factory=list)
    neaps: list[NotableEventAggregationPolicy] = field(default_factory=list)

    def add_service(self, svc: Service) -> None:
        self.services.append(svc)

    def to_dict(self) -> dict:
        """Serialize to ITSI content pack import format."""
        return {
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "_key": self._key,
            "data": {
                "services": [s.to_dict() for s in self.services],
                "entities": [e.to_dict() for e in self.entities],
                "kpi_base_searches": [
                    {
                        "_key": k._key,
                        "title": k.title,
                        "base_search": k.base_search,
                        "metric_qualifier": k.metric_qualifier,
                        "entity_id_fields": k.entity_id_fields,
                    }
                    for k in self.kpi_base_searches
                ],
                "kpi_threshold_templates": [
                    {
                        "_key": t._key,
                        "title": t.title,
                        "thresholds": t.thresholds,
                    }
                    for t in self.threshold_templates
                ],
            },
        }

    def to_neap_bundle(self) -> dict:
        """
        Serialize correlation searches + NEAPs as a separate JSON bundle.
        This is loaded via the ITSI REST API or packaged into a Splunk app,
        NOT via the content pack import endpoint.
        """
        return {
            "title": self.title,
            "_pack_key": self._key,
            "correlation_searches": [cs.to_dict() for cs in self.correlation_searches],
            "notable_event_aggregation_policies": [n.to_dict() for n in self.neaps],
        }
