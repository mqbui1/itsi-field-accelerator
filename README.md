# ITSI Field Accelerator

A CLI tool that collapses weeks of ITSI onboarding prep into minutes — using Claude AI
to generate service trees, KPIs, and content packs from plain-English descriptions,
ServiceNow CMDB exports, or pre-built vertical templates.

> Built to bridge the gap until Splunk's native AI-driven CMDB discovery ships.
> Works today, on-prem and cloud.

---

## The Problem: Blank Canvas Paralysis

Standing up Splunk ITSI traditionally requires:

| Step | Manual effort | Time |
|------|--------------|------|
| Service decomposition | 2-4 consultant workshops | 1-3 weeks |
| KPI identification | Manual discovery per service type | 1-2 weeks |
| SPL authoring | Deep Splunk expertise required | 1-2 weeks |
| Entity mapping | Error-prone linking of CIs to services | Days |
| Threshold configuration | Manual tuning or ML baseline wait | 1 week |

**Total: 4-12 weeks before a customer sees meaningful service health.**

Splunk's AI-driven service discovery shipped in ITSI 5.0.3 for Cloud customers. But
CMDB-first workflows (ServiceNow → service tree) and on-premises parity are on the
roadmap for a future phase with no committed date. This tool fills that gap now.

---

## How It Works

```
  Plain-English           ┌─────────────────────────────────────────┐
  description  ──────────►│                                         │
                           │   Claude AI                             │──► ITSI service tree
  SNOW CMDB    ──────────►│   (service discovery + KPI generation) │    + KPIs + SPL
  CSV / JSON               │                                         │──► Ready to import
                           │   Template library fallback             │    via UI or REST API
  Vertical name ──────────►│   (30+ KPIs, 9 service types)          │
                           │                                         │
  Existing pack ──────────►│   AI enrichment (gap-fill + improve)   │
                           └─────────────────────────────────────────┘
```

---

## Commands

| Command | Mode | What it does |
|---------|------|-------------|
| `discover` | **AI** | Describe your architecture in plain English → Claude generates a full service tree with custom KPIs and SPL |
| `enrich` | **AI** | Claude reviews an existing content pack, fills coverage gaps, improves KPIs, adds missing services |
| `cmdb` | Template + optional AI | Parse a SNOW CMDB export → service tree with matched KPI templates; `--ai-infer` for Claude CI-type inference |
| `bootstrap` | Template | Generate a demo-ready pack from a pre-built vertical template (banking, healthcare, retail, etc.) |
| `kpi-discover` | Template + optional AI | Show KPI templates for a service type; `--ai` for Claude-generated custom KPIs |
| `preflight` | Live check | Verify Splunk has the indexed data needed for ITSI onboarding |
| `import` | Live push | Push a generated content pack into live ITSI via REST API |

---

## Install

```bash
git clone https://github.com/mqbui1/itsi-field-accelerator.git
cd itsi-field-accelerator
pip install -r requirements.txt
```

**Requirements:** Python 3.9+, `anthropic`, `click`, `rich`, `requests`, `boto3`

---

## AI Provider Configuration

The tool auto-detects which AI backend to use — no flag needed.

### Option 1: Anthropic API (default if key present)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Option 2: AWS Bedrock

No API key needed — uses your existing AWS credentials. Ideal for teams already running
workloads in AWS or organizations with Bedrock access through enterprise agreements.

```bash
# Any standard AWS credential method works:
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1   # optional, defaults to us-east-1

# Or use a named profile:
export AWS_PROFILE=my-profile

# Or attach an IAM role (EC2/ECS/Lambda) — no env vars needed at all.
```

The default Bedrock model is `us.anthropic.claude-3-5-sonnet-20241022-v2:0` (Claude 3.5 Sonnet v2).
Override with `BEDROCK_MODEL_ID` if your account uses a different model ID or cross-region inference prefix.

```bash
export BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

**Force a specific provider** (overrides auto-detection):

```bash
export ITSI_AI_PROVIDER=bedrock     # always use Bedrock
export ITSI_AI_PROVIDER=anthropic   # always use Anthropic API
```

**Auto-detection order:**
1. `ITSI_AI_PROVIDER` env var (explicit override)
2. `ANTHROPIC_API_KEY` present → Anthropic API
3. Fallback → AWS Bedrock (standard credential chain)

---

## AI Commands

### `discover` — plain English to full content pack

Describe your application architecture and Claude generates a complete ITSI content
pack with services, dependencies, and KPIs — tailored to your specific stack,
industry, and SLA requirements.

```bash
python -m itsi_accelerator discover \
  --description "Java Spring Boot microservices on Kubernetes: payments API, fraud
    scoring engine, account management, notifications. PostgreSQL for accounts,
    Redis cache, Kafka for async events. Needs 99.9% SLA on payments." \
  --context "FSI / banking, PCI-DSS compliance required" \
  --output banking_pack.json \
  --index prod
```

**What Claude does:**
1. Parses the architecture into a hierarchical service model (business → app → platform → infra)
2. Infers service types (api_gateway, payment_processor, fraud_detection, etc.)
3. Identifies SLA-critical services and flags them for tighter KPI thresholds
4. Generates 4-6 custom KPIs per service with real, runnable SPL tailored to each service type
5. Wires parent-child dependencies based on the described call paths
6. Flags monitoring coverage gaps (missing data sources, compliance blind spots)

**Example output (truncated):**

```
Architecture: A PCI-DSS-compliant FSI digital banking platform built on Java Spring Boot
microservices orchestrated by Kubernetes. The monitoring strategy prioritizes the 99.9% SLA
on the Payment Processing service tree, with fraud detection and authentication treated as
equally critical synchronous dependencies.

Discovered 16 services:
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Service                         ┃ KPIs ┃ Tags                                ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Digital Banking Platform        │    0 │ ai-discovered, business             │
│ Payment Processing              │    5 │ ai-discovered, application          │
│ Fraud Scoring                   │    5 │ ai-discovered, application          │
│ Account Management              │    5 │ ai-discovered, application          │
│ Payments API Gateway            │    5 │ ai-discovered, application          │
│ Event Streaming (Kafka)         │    5 │ ai-discovered, platform             │
│ PostgreSQL Database             │    5 │ ai-discovered, platform             │
│ Redis Cache                     │    5 │ ai-discovered, platform             │
│ Kubernetes Platform             │    5 │ ai-discovered, infrastructure       │
│ ...                             │      │                                     │
└─────────────────────────────────┴──────┴─────────────────────────────────────┘

Coverage gaps flagged by Claude:
  • No APM / distributed tracing source mentioned — latency root-cause across
    Spring Boot services will be blind without it
  • No Kafka broker metrics source defined — JMX or Kafka exporter needed for
    consumer-lag and under-replicated-partition KPIs
  • PCI-DSS audit log ingestion not described — cardholder data environment
    logs must flow into a separate, access-controlled index
  • No synthetic / outside-in monitoring described — external payment API
    health-check essential for validating the 99.9% SLA
```

Use `--template-kpis` to skip AI KPI generation and use curated templates instead
(faster, still uses Claude for service tree discovery).

---

### `enrich` — AI review and improvement of any content pack

Claude analyzes an existing pack (from `cmdb`, `bootstrap`, or `discover`),
identifies gaps, adds missing KPIs, improves generic SPL, and flags missing services.

```bash
python -m itsi_accelerator enrich \
  --pack banking_pack.json \
  --output banking_enriched.json \
  --index prod
```

```bash
# Just get a written review without modifying the pack:
python -m itsi_accelerator enrich --pack banking_pack.json --review-only
```

Claude assesses:
- **Golden signal coverage**: latency, errors, traffic, saturation per service
- **SPL quality**: is it specific enough, or too generic to be useful?
- **Dependency completeness**: are call-path relationships accurately modeled?
- **Threshold calibration**: are thresholds set, and appropriate for criticality?
- **Missing services**: obvious tiers or components not in the pack
- **Coverage score**: 0-100 overall monitoring coverage rating

---

### `cmdb` with `--ai-infer`

When your CMDB export has missing or generic `sys_class_name` values, Claude
infers the correct service type from each CI's name and description.

```bash
python -m itsi_accelerator cmdb \
  --input cmdb_export.csv \
  --output itsi_pack.json \
  --ai-infer
```

```
Claude inferred types for 7 CIs:
  payments-orchestrator → payment_processor  (high confidence)
  fraud-ml-svc          → fraud_detection    (high confidence)
  redis-cluster-01      → database           (medium confidence)
  ...
```

---

### `kpi-discover` with `--ai`

Generate custom KPIs via Claude instead of static templates. Useful when you
have specific sourcetypes or field names to work with.

```bash
python -m itsi_accelerator kpi-discover \
  --service-type payment_processor \
  --description "Stripe-based payment gateway processing card transactions, ACH, and wire transfers" \
  --index payments \
  --ai
```

---

## Template Commands

### `bootstrap` — demo vertical templates

Generates a complete ITSI content pack from a pre-built vertical bundle.
No CMDB data or Splunk connection needed — ideal for demos and PoVs.

```bash
python -m itsi_accelerator bootstrap --vertical banking --output demo.json
```

**Available verticals:**

| Vertical | Services | Use case |
|----------|----------|----------|
| `banking` | Retail Banking Platform — web portal, mobile API, payments, fraud, auth, core DB, Kafka | FSI banking demos |
| `healthcare` | Patient Care Platform — patient portal, EMR, claims, lab results, HL7 queue | Healthcare / payer demos |
| `retail` | E-Commerce Platform — storefront, order mgmt, inventory, payment gateway, fraud | Retail / CPG demos |
| `telecom` | Subscriber Platform — BSS/OSS, billing, provisioning, subscriber DB | Telco / cable demos |
| `manufacturing` | Smart Factory Platform — MES, ERP integration, QMS, SCADA bus | Industrial / OT demos |
| `generic` | 3-tier web app — web, API gateway, app tier, auth, DB, cache, message bus | Generic demo / PoV |

---

### `cmdb` — SNOW export to service tree

```bash
python -m itsi_accelerator cmdb \
  --input cmdb_export.csv \
  --output itsi_pack.json \
  --title "Acme Banking Platform" \
  --index main
```

**Supported CSV columns** (auto-detected, case-insensitive):

| Column | Aliases |
|--------|---------|
| `name` | `sys_name`, `ci_name`, `display_name` |
| `sys_class_name` | `class`, `ci_class`, `type` |
| `parent` | `parent_ci`, `parent_name`, `u_parent` |
| `business_service` | `business_service_name`, `biz_service` |
| `environment` | `env`, `u_environment` |
| `short_description` | `description` |

**CI class → KPI template mapping:**

| SNOW CI Class | KPIs Applied |
|---|---|
| `cmdb_ci_web_server` | HTTP error rate, response time, RPS |
| `cmdb_ci_app_server` | App error rate, JVM heap, thread pool queue |
| `cmdb_ci_database` | Query latency, active connections, replication lag, failed txns |
| `cmdb_ci_linux_server` | CPU, memory, disk utilization |
| `cmdb_ci_k8s_cluster` | Pod restarts, availability %, CPU throttling |
| `cmdb_ci_mq_server` | Consumer lag, messages per second |

---

### `preflight` — data readiness check

```bash
python -m itsi_accelerator preflight \
  --url https://splunk.example.com:8089 \
  --token <splunk_token>
```

Checks: connectivity, metric indexes present, host entities discoverable,
recognized sourcetypes, data freshness. Returns a 0-100 readiness score.

---

### `import` — push into live ITSI

```bash
python -m itsi_accelerator import \
  --pack itsi_pack.json \
  --url https://splunk.example.com:8089 \
  --token <splunk_token>
```

Or import via ITSI UI: **Configuration → Data Integrations → Content Library → Import**

---

## Content Pack Format

Generated packs follow the ITSI content pack schema and import cleanly via
the ITSI UI or REST API (`POST /servicesNS/nobody/SA-ITOA/itsi/content_packs/import`).

Each pack includes:
- **Services** with title, description, entity rules, dependency wiring, tags
- **KPIs** with SPL, metric name, unit, aggregation method, threshold suggestions
- **ServiceHealthScore** auto-added to every service
- **Parent-child dependency** relationships from CMDB or AI-discovered topology

AI-generated KPIs are tagged `_enriched_by_ai: true`. AI-suggested missing services
are tagged `ai-suggested` for easy review before production activation.

---

## Project Structure

```
itsi-field-accelerator/
├── itsi_accelerator/
│   ├── ai/
│   │   ├── claude_client.py      # Anthropic SDK wrapper (tool_use + streaming)
│   │   ├── service_discoverer.py # Architecture description → service tree
│   │   ├── kpi_generator.py      # Service context → custom KPIs with SPL
│   │   ├── pack_enricher.py      # Review + gap-fill an existing pack
│   │   └── cmdb_enricher.py      # Infer CI types for unclassified CIs
│   ├── cli/main.py               # All CLI commands (click + rich)
│   ├── cmdb/parser.py            # SNOW CSV/JSON → ContentPack
│   ├── templates/
│   │   ├── kpi_library.py        # 30+ KPI templates, 9 service types, full SPL
│   │   └── verticals.py          # 6 pre-built vertical bundles
│   ├── preflight/checker.py      # Splunk data readiness (5 checks, scored)
│   └── core/
│       ├── models.py             # ContentPack, Service, KPI data models
│       └── importer.py           # ITSI REST API importer
└── examples/sample_cmdb_export.csv
```

---

## Relationship to ITSI 5.0.3 AI Discovery

Splunk shipped AI-Driven Service & KPI Discovery in ITSI 5.0.3 for Cloud customers.
This tool is complementary, not competitive:

| Capability | ITSI 5.0.3 AI Discovery | This tool |
|------------|------------------------|-----------|
| Works on-premises | Phase 2/3 (TBD) | Now |
| CMDB as primary input | Phase 3 (TBD) | Now |
| Works without indexed data | No | Yes (`discover`, `bootstrap`) |
| AI-generated SPL | Yes (from indexed data) | Yes (from description + context) |
| Wizard-based UI | Yes | CLI |
| Demo environment setup | No | Yes (`bootstrap`) |
| Pack gap analysis + enrichment | No | Yes (`enrich`) |

Use ITSI 5.0.3 AI Discovery for Cloud deployments with existing indexed data.
Use this tool for on-prem, CMDB-first, pre-data, and demo/PoV scenarios.

---

## Contributing

**Adding a new service type (template path):**
1. Add entries to `KPI_TEMPLATES` in `itsi_accelerator/templates/kpi_library.py`
2. Add CI class aliases to `CI_CLASS_ALIASES`
3. Optionally add the service type to a vertical in `verticals.py`

**Adding a new vertical:**
Add an entry to `VERTICALS` in `itsi_accelerator/templates/verticals.py` following
the existing pattern (list of CI dicts with `name`, `ci_class`, `parent`, `business_service`).

PRs welcome for new service types, verticals, CI class mappings, and AI prompt improvements.

---

*Built by Marc Bui — Splunk Solutions Architect*
