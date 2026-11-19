# ITSI Field Accelerator

> **AI-driven ITSI onboarding** — from plain-English architecture description or ServiceNow CMDB export
> to a fully populated, ready-to-import ITSI content pack in minutes, not weeks.

Built to bridge the gap until Splunk's native AI-driven CMDB discovery ships.
Works today, on-prem and cloud, with **Anthropic API or AWS Bedrock**.

---

## The Problem: Blank Canvas Paralysis

Standing up Splunk ITSI traditionally requires:

| Step | Manual effort | Time |
|------|--------------|------|
| Service decomposition | 2–4 consultant workshops | 1–3 weeks |
| KPI identification | Manual discovery per service type | 1–2 weeks |
| SPL authoring | Deep Splunk expertise required | 1–2 weeks |
| Entity mapping | Error-prone linking of CIs to services | Days |
| Threshold configuration | Manual tuning or ML baseline wait | 1 week |

**Total: 4–12 weeks before a customer sees meaningful service health.**

This isn't anecdotal — Splunk's own product team named it "Blank Canvas Paralysis" in internal documentation.
It's the leading reason customers stall after licensing ITSI and a known 6–9 month churn signal.

Splunk shipped AI-Driven Service & KPI Discovery in ITSI 5.0.3 for Cloud customers — but CMDB-first
workflows (ServiceNow → service tree) and on-premises parity remain on the roadmap with no committed date.
**This tool fills that gap today.**

---

## How the AI Works

The tool uses **Claude** (via Anthropic API or AWS Bedrock) as the core reasoning engine.
Every AI command uses Claude's [tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
capability to produce structured, schema-validated output — not free-text that needs parsing.

```
  Your input                    Claude AI pipeline                    Output
  ──────────────────────────    ──────────────────────────────────    ────────────────────────
  Plain-English description ──► Step 1: Service tree discovery    ──► Hierarchical service model
                                  (architecture → services,             business / app / platform
                                   CI types, SLA flags, deps)           / infra tiers

                            ──► Step 2: KPI generation per svc   ──► 4–6 KPIs per service
                                  (service context → golden            with real, runnable SPL
                                   signal SPL, thresholds)             tailored to each type

  SNOW CMDB CSV/JSON        ──► CI type inference (--ai-infer)   ──► Missing ci_class filled in
                                  (name + description → type)         with confidence score

  Existing content pack     ──► Step 1: Coverage assessment      ──► services_needing_kpis[]
                                  (flat schema, reliable output)       missing_services[]
                                                                        coverage_score 0–100
                            ──► Step 2: Gap fill per service     ──► New KPIs added to pack
                                  (same KPI generator as above)
```

### Why two-step for enrichment?

Claude reliably populates flat schemas. Deeply nested schemas
(e.g. `service_improvements[].new_kpis[].thresholds`) cause it to return empty arrays.
The `enrich` pipeline uses a deliberately simple assessment schema in Step 1 to get
a stable list of flagged services, then calls the KPI generator independently per service in Step 2.
This is why enrichment works reliably across all pack sizes.

### What Claude understands natively

**Service types** (inferred from names, descriptions, and architecture context):

| Type | Examples |
|------|----------|
| `api_gateway` | Kong, AWS API GW, NGINX reverse proxy |
| `app_server` | Spring Boot, Node.js, Django, .NET |
| `payment_processor` | Stripe gateway, ACH processor, card auth |
| `fraud_detection` | ML scoring engine, rules engine |
| `auth_service` | OAuth provider, LDAP, Okta connector |
| `database` | PostgreSQL, MySQL, Oracle, Cosmos DB |
| `message_queue` | Kafka, RabbitMQ, SQS, Azure Service Bus |
| `kubernetes` | K8s cluster, EKS, GKE, AKS |
| `linux_host` | EC2, bare metal, VM hosts |

**Golden signals per service type** (what Claude checks coverage for):

| Signal | What it measures |
|--------|-----------------|
| **Latency** | p50/p95/p99 response time, DB query time |
| **Traffic** | Requests/sec, messages/sec, transactions/min |
| **Errors** | HTTP 5xx rate, exception rate, failed transactions |
| **Saturation** | CPU/memory/connection pool utilization, queue depth |

---

## Quickstart

```bash
git clone https://github.com/mqbui1/itsi-field-accelerator.git
cd itsi-field-accelerator
pip install -r requirements.txt

# No API key needed — bootstrap works without AI:
python -m itsi_accelerator bootstrap --vertical banking --output demo.json

# AI mode — set your credentials (see "AI Provider" below), then:
python -m itsi_accelerator discover \
  --description "Java Spring Boot on Kubernetes: payments API, fraud scoring, PostgreSQL, Redis, Kafka. 99.9% SLA on payments." \
  --context "FSI / banking, PCI-DSS required" \
  --output banking_pack.json
```

**Requirements:** Python 3.9+, `anthropic`, `click`, `rich`, `requests`, `boto3`

---

## AI Provider

The tool auto-detects which AI backend to use — no code changes or flags needed.

### Option 1: Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Option 2: AWS Bedrock

No separate API key needed — uses your existing AWS credentials. Ideal for teams already
running workloads in AWS or organizations with Bedrock access through enterprise agreements.

```bash
# Any standard AWS credential method works:
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1   # optional, defaults to us-east-1

# Or use a named profile:
export AWS_PROFILE=my-profile

# Or attach an IAM role (EC2 / ECS / Lambda) — no env vars needed at all.
```

Default Bedrock model: `us.anthropic.claude-3-5-sonnet-20241022-v2:0`

```bash
# Override model or force a provider:
export BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
export ITSI_AI_PROVIDER=bedrock     # force Bedrock even if ANTHROPIC_API_KEY is set
export ITSI_AI_PROVIDER=anthropic   # force Anthropic API
```

**Auto-detection order:**
1. `ITSI_AI_PROVIDER` env var (explicit override)
2. `ANTHROPIC_API_KEY` present → Anthropic API
3. Fallback → AWS Bedrock (standard credential chain)

---

## Commands

| Command | Mode | What it does |
|---------|------|-------------|
| `discover` | **AI** | Describe your architecture → Claude generates a full service tree with custom KPIs and SPL |
| `enrich` | **AI** | Claude reviews a content pack, fills coverage gaps, adds missing services, scores 0–100 |
| `cmdb` | Template + optional AI | Parse a SNOW CMDB export → service tree; `--ai-infer` for Claude CI-type inference |
| `bootstrap` | Template | Generate a demo-ready pack from a pre-built vertical (no AI needed) |
| `kpi-discover` | Template + optional AI | Show KPI templates for a service type; `--ai` for Claude-generated custom KPIs |
| `preflight` | Live check | Verify Splunk has the indexed data needed for ITSI onboarding |
| `import` | Live push | Push a generated content pack into live ITSI via REST API |

---

## AI Commands

### `discover` — plain English to full content pack

Describe your application architecture and Claude generates a complete ITSI content pack
with services, dependencies, and KPIs — tailored to your specific stack, industry, and SLA requirements.

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
2. Infers service types (`api_gateway`, `payment_processor`, `fraud_detection`, etc.)
3. Identifies SLA-critical services and flags them for tighter KPI thresholds
4. Generates 4–6 custom KPIs per service with real, runnable SPL tailored to each service type
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

### `enrich` — AI review and gap-fill of any existing content pack

Claude analyzes a pack from any source (`cmdb`, `bootstrap`, `discover`, or hand-built),
identifies gaps, adds missing KPIs, and flags missing services. Uses a two-step AI pipeline
(coverage assessment → per-service KPI generation) for reliable structured output.

```bash
python -m itsi_accelerator enrich \
  --pack banking_pack.json \
  --output banking_enriched.json \
  --index prod
```

```bash
# Just get a written narrative review without modifying the pack:
python -m itsi_accelerator enrich --pack banking_pack.json --review-only
```

**What Claude assesses:**
- **Golden signal coverage**: latency, errors, traffic, saturation per service
- **SPL quality**: is it specific enough to be actionable, or too generic?
- **Dependency completeness**: are call-path relationships accurately modeled?
- **Missing services**: obvious tiers or components not in the pack
- **Coverage score**: 0–100 overall monitoring coverage rating

**Example output:**
```
Coverage score: 54/100
Summary: The pack covers application-layer services well but is missing infrastructure
and platform KPIs. Kubernetes cluster health, Redis saturation, and Kafka consumer-lag
signals are absent. 4 services flagged for improvement; 2 missing services identified.

Applying 4 service improvements + 2 new services...

Remaining gaps:
  • No synthetic monitoring — external SLA validation not covered
  • Kafka partition-replication health not instrumented
```

---

### `cmdb` with `--ai-infer` — smarter CI type inference

Standard CMDB ingestion maps `sys_class_name` to KPI templates. When values are missing,
generic, or use custom naming conventions, `--ai-infer` lets Claude classify each CI from
its name and description instead.

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

### `kpi-discover` with `--ai` — custom KPIs for any service type

Generate KPIs via Claude instead of static templates. Useful when you have specific
sourcetypes, field names, or non-standard technology to work with.

```bash
python -m itsi_accelerator kpi-discover \
  --service-type payment_processor \
  --description "Stripe-based payment gateway processing card transactions, ACH, and wire transfers" \
  --index payments \
  --ai
```

---

## Template Commands (no AI required)

### `bootstrap` — demo vertical templates

Generates a complete ITSI content pack from a pre-built vertical bundle. No CMDB data,
Splunk connection, or API key needed — the fastest way to get a working ITSI demo loaded.

```bash
python -m itsi_accelerator bootstrap --vertical banking --output demo.json
```

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
recognized sourcetypes, data freshness. Returns a 0–100 readiness score.

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
│   │   ├── claude_client.py      # Provider auto-detection (Anthropic API + AWS Bedrock)
│   │   ├── service_discoverer.py # Architecture description → service tree (tool_use)
│   │   ├── kpi_generator.py      # Service context → custom KPIs with SPL (tool_use)
│   │   ├── pack_enricher.py      # Two-step assessment + gap-fill pipeline
│   │   └── cmdb_enricher.py      # Infer CI types for unclassified CIs (tool_use)
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
| Works on-premises | Phase 2/3 (TBD) | **Now** |
| CMDB as primary input (ServiceNow) | Phase 3 (TBD) | **Now** |
| Works without indexed data | No | **Yes** (`discover`, `bootstrap`) |
| AI-generated SPL | Yes (from indexed data) | **Yes** (from description + context) |
| AWS Bedrock as AI backend | No | **Yes** |
| Wizard-based UI | Yes | CLI |
| Demo environment setup | No | **Yes** (`bootstrap`) |
| Pack gap analysis + enrichment | No | **Yes** (`enrich`) |
| Coverage scoring | No | **Yes** (0–100) |

Use ITSI 5.0.3 AI Discovery for Cloud deployments with existing indexed data.
Use this tool for on-prem, CMDB-first, pre-data, demo/PoV, and pack improvement scenarios.

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
