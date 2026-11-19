# ITSI Field Accelerator

A CLI tool that collapses weeks of ITSI onboarding prep into minutes — generating
service trees, KPI mappings, and content packs from your ServiceNow CMDB export or
a pre-built vertical template.

> Built to bridge the gap until Splunk's native AI-driven CMDB discovery ships.
> Works today, on-prem and cloud.

---

## The Problem: Blank Canvas Paralysis

Standing up Splunk ITSI traditionally requires:

| Step | Manual effort | Time |
|------|--------------|------|
| Service decomposition | 2-4 consultant workshops | 1-3 weeks |
| KPI identification | Manual discovery per service type | 1-2 weeks |
| SPL authoring for KPIs | Deep Splunk expertise required | 1-2 weeks |
| Entity mapping | Error-prone linking of CIs to services | Days |
| Threshold configuration | Manual tuning or waiting for ML baseline | 1 week |

**Total: 4-12 weeks before a customer sees meaningful service health.**

Splunk's product team is building AI-driven service discovery into ITSI — it shipped
for Cloud customers in ITSI 5.0.3. But CMDB-first workflows (ServiceNow -> service tree)
and on-premises parity are on the roadmap for a future phase with no committed date.

This tool fills that gap now.

---

## What It Does

```
                  ┌──────────────────────────────────────────────────┐
  SNOW CMDB CSV   │                                                  │
  ──────────────► │   ITSI Field Accelerator                        │──► itsi_pack.json
                  │                                                  │
  Vertical name   │  • CMDB parser (CI class → service type)        │──► Ready to import
  ──────────────► │  • KPI template library (30+ templates, 9 types)│    into ITSI via UI
                  │  • Service tree builder (parent/child deps)      │    or REST API
  Splunk creds    │  • Pre-flight data checker                      │
  ──────────────► │  • ITSI REST API importer                       │
                  │                                                  │
                  └──────────────────────────────────────────────────┘
```

**Four commands:**

| Command | What it does |
|---------|-------------|
| `cmdb` | Parse a ServiceNow CMDB export and generate an ITSI content pack with services, KPIs, entity rules, and dependency wiring |
| `bootstrap` | Generate a full demo-ready content pack from a pre-built vertical template (no CMDB needed) |
| `kpi-discover` | Show recommended KPI templates for any service type or CI class |
| `preflight` | Check if a Splunk instance has the indexed data needed for ITSI onboarding |

---

## Install

```bash
git clone https://github.com/mqbui1/itsi-field-accelerator.git
cd itsi-field-accelerator
pip install -r requirements.txt
```

**Requirements:** Python 3.9+, `click`, `rich`, `requests`

---

## Usage

### cmdb — SNOW export to ITSI service tree

Takes a ServiceNow CMDB export (CSV or JSON) and generates an ITSI content pack
with services, KPIs, entity rules, and dependency relationships fully wired.

```bash
python -m itsi_accelerator cmdb \
  --input cmdb_export.csv \
  --output itsi_content_pack.json \
  --title "Acme Corp Banking Platform" \
  --index main
```

**Supported CSV columns** (auto-detected, case-insensitive):

| Column | Aliases | Required |
|--------|---------|----------|
| `name` | `sys_name`, `ci_name`, `display_name` | Yes |
| `sys_class_name` | `class`, `ci_class`, `type` | Yes |
| `parent` | `parent_ci`, `parent_name`, `u_parent` | No |
| `business_service` | `business_service_name`, `biz_service` | No |
| `environment` | `env`, `u_environment` | No |
| `short_description` | `description` | No |

**Example CSV:**
```csv
name,sys_class_name,parent,business_service,environment,short_description
Online Banking Portal,cmdb_ci_web_server,,Retail Banking Platform,production,Customer web portal
Payment Service,cmdb_ci_app_server,,Retail Banking Platform,production,Payment orchestration
Core Banking DB,cmdb_ci_database,Payment Service,Retail Banking Platform,production,Primary PostgreSQL
```

**ServiceNow CI class mapping:**

| SNOW CI Class | Service Type | KPI Templates Applied |
|---|---|---|
| `cmdb_ci_web_server` | web_server | HTTP error rate, response time, RPS |
| `cmdb_ci_app_server` | app_server | Error rate, JVM heap, thread pool |
| `cmdb_ci_database` | database | Query latency, connections, replication lag |
| `cmdb_ci_linux_server` | linux_host | CPU, memory, disk utilization |
| `cmdb_ci_k8s_cluster` | kubernetes | Pod restarts, availability, CPU throttling |
| `cmdb_ci_mq_server` | message_queue | Consumer lag, message rate |
| `cmdb_ci_apigee` | api_gateway | Error rate, P95 latency, rate limit hits |

---

### bootstrap — demo environment from vertical template

Generates a complete ITSI content pack from a pre-built vertical template.
No CMDB data or Splunk connection needed. Useful for demos, workshops, and PoVs.

```bash
python -m itsi_accelerator bootstrap \
  --vertical banking \
  --output demo_pack.json
```

**Available verticals:**

| Vertical | Services | Use case |
|----------|----------|----------|
| `banking` | Retail Banking Platform — web portal, mobile API, payments, fraud, auth, core banking DB, Kafka | FSI banking demos |
| `healthcare` | Patient Care Platform — patient portal, EMR, claims, lab results, HL7 queue | Healthcare / payer demos |
| `retail` | E-Commerce Platform — storefront, order mgmt, inventory, payment, fraud | Retail / CPG demos |
| `telecom` | Subscriber Platform — BSS, billing, provisioning, subscriber DB | Telco / cable demos |
| `manufacturing` | Smart Factory Platform — MES, ERP integration, QMS, SCADA bus | Industrial / OT demos |
| `generic` | 3-tier web app — web, API gateway, app tier, auth, DB, cache, message bus | Generic demo / PoV |

---

### kpi-discover — KPI recommendations for any service type

Shows recommended KPI templates for a given service type, including SPL, metric
name, unit, and suggested thresholds. Use this to plan KPI coverage before onboarding.

```bash
python -m itsi_accelerator kpi-discover \
  --service-type payment_processor \
  --index main \
  --output payment_kpis.json
```

**All supported service types:**
`web_server`, `app_server`, `database`, `linux_host`, `kubernetes`,
`message_queue`, `api_gateway`, `payment_processor`, `fraud_detection`, `auth_service`

**Example output:**
```
                KPI Templates: payment_processor
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ KPI Title                 ┃ Metric              ┃ Unit  ┃ Yellow        ┃ Red           ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ Transaction Decline Rate  │ decline_pct         │ %     │ 2             │ 10            │
│ Payment Processing Latency│ avg_latency         │ ms    │ 2000          │ 5000          │
│ Failed Settlements        │ failed_settlements  │ count │ 1             │ 5             │
└───────────────────────────┴─────────────────────┴───────┴───────────────┴───────────────┘
```

---

### preflight — data readiness check

Connects to Splunk and runs a readiness check before starting ITSI onboarding.
Answers: "Is the right data already in Splunk?"

```bash
python -m itsi_accelerator preflight \
  --url https://splunk.example.com:8089 \
  --token <splunk_token> \
  --output preflight_report.json
```

**Checks run:**

| Check | What it looks for |
|-------|------------------|
| Connectivity | Splunk REST API reachable, auth valid, Splunk version |
| Metric indexes | `em_metrics`, `itsi_im_metrics`, `metrics`, or `perf` present |
| Host entities | Hosts discoverable via CPU/memory metric dimensions |
| Sourcetypes | Recognized ITSI-compatible sourcetypes (`access_combined`, `kube:events`, etc.) |
| Data freshness | Data present and recently updated |

**Score interpretation:**
- 80-100%: Ready for ITSI onboarding
- 50-79%: Partial — some data onboarding needed first
- <50%: Not ready — address failing checks before proceeding

---

### import — push content pack into live ITSI

```bash
python -m itsi_accelerator import \
  --pack itsi_content_pack.json \
  --url https://splunk.example.com:8089 \
  --token <splunk_token>
```

Alternatively, import via ITSI UI: **Configuration > Data Integrations > Content Library > Import**

---

## Content Pack Format

Generated packs follow the ITSI content pack schema and can be imported via:
- ITSI UI (Configuration > Data Integrations > Content Library)
- REST API: `POST /servicesNS/nobody/SA-ITOA/itsi/content_packs/import`
- This tool's `import` command

Each pack includes:
- **Services** with title, description, entity rules, dependency wiring, and tags
- **KPIs** with SPL, metric name, unit, aggregation method, and threshold suggestions
- **ServiceHealthScore** KPI auto-added to every service
- **Parent-child dependency** relationships from CMDB `parent` column

---

## Project Structure

```
itsi-field-accelerator/
├── itsi_accelerator/
│   ├── __main__.py              # python -m itsi_accelerator entry point
│   ├── cli/
│   │   └── main.py              # CLI commands (click + rich)
│   ├── cmdb/
│   │   └── parser.py            # SNOW CSV/JSON -> ContentPack
│   ├── templates/
│   │   ├── kpi_library.py       # 30+ KPI templates across 9 service types
│   │   └── verticals.py         # 6 pre-built vertical bundles
│   ├── preflight/
│   │   └── checker.py           # Splunk data readiness checks
│   └── core/
│       ├── models.py            # ContentPack, Service, KPI data models
│       └── importer.py          # ITSI REST API importer
├── examples/
│   └── sample_cmdb_export.csv   # Sample input for testing
└── requirements.txt
```

---

## Relationship to ITSI 5.0.3 AI Discovery

Splunk shipped AI-Driven Service & KPI Discovery in ITSI 5.0.3 for Cloud customers.
This tool is complementary, not competitive:

| Capability | ITSI 5.0.3 AI Discovery | This tool |
|------------|------------------------|-----------|
| Works on-premises | Phase 2/3 (TBD) | Now |
| CMDB as primary input | Phase 3 (TBD) | Now |
| Works without indexed data | No | Yes (bootstrap mode) |
| AI-generated SPL | Yes | Curated templates |
| Wizard-based UI | Yes | CLI |
| Demo environment setup | No | Yes |

Use ITSI 5.0.3 AI Discovery for Cloud deployments with existing indexed data.
Use this tool for on-prem, CMDB-first, and demo/PoV scenarios.

---

## Contributing

KPI templates and vertical definitions live in `itsi_accelerator/templates/`.
Adding a new service type:

1. Add a template entry to `KPI_TEMPLATES` in `kpi_library.py`
2. Add CI class aliases to `CI_CLASS_ALIASES`
3. Optionally add the service type to a vertical in `verticals.py`

PRs welcome for new service types, verticals, and CI class mappings.

---

*Built by Marc Bui — Splunk Solutions Architect*
