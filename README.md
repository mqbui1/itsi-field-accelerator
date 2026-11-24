# ITSI Field Accelerator

> **AI-driven ITSI onboarding and demo automation** — from architecture diagram, plain-English
> description, live APM topology, or ServiceNow CMDB export to a fully populated, demo-ready
> ITSI environment in minutes, not weeks.

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
| Episode management (NEAPs) | Per-service configuration in UI | Days |

**Total: 4–12 weeks before a customer sees meaningful service health.**

This isn't anecdotal — Splunk's own product team named it "Blank Canvas Paralysis" in internal
documentation. It's the leading reason customers stall after licensing ITSI and a known 6–9
month churn signal.

---

## Quickstart

```bash
git clone https://github.com/mqbui1/itsi-field-accelerator.git
cd itsi-field-accelerator
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # or AWS Bedrock — see AI Provider below
```

**OTel Demo (fastest path — 3 commands):**

```bash
# 1. One-time setup: build pack → NEAPs → import to ITSI → probe readiness
python -m itsi_accelerator setup \
  --vertical otel-demo \
  --url https://my-show.splunkcloud.com \
  --token $SPLUNK_TOKEN

# 2. During the demo — live readiness board on a second monitor
python -m itsi_accelerator probe \
  --url https://my-show.splunkcloud.com --token $SPLUNK_TOKEN --watch

# 3. Break something (and watch ITSI react)
python -m itsi_accelerator degrade --vertical otel-demo --target otel-demo
```

**Requirements:** Python 3.9+, `anthropic`, `click`, `rich`, `requests`, `boto3`

---

## Demo Flow

**Simple path (OTel Demo / known verticals):**

```
setup --vertical otel-demo --url ... --token ...
  └── Step 1: Bootstrap content pack from template  (no AI)
  └── Step 2: Generate NEAPs + correlation searches  (Claude, one call)
  └── Step 3: Import pack to ITSI via REST API
  └── Step 4: Probe readiness → prints verdict + next steps

degrade --vertical otel-demo --target otel-demo   ← inject during demo
probe --watch                                      ← monitor on second monitor
```

**Advanced path (custom / customer architectures):**

```
1. Build the content pack
   diagram -i architecture.png          ← from an architecture diagram (most impressive)
   apm --realm us1 --environment prod   ← from your live O11y APM service map
   discover -d "Spring Boot on K8s..."  ← from plain English
   cmdb -i export.csv                   ← from ServiceNow CMDB

2. Add episode management
   neap --pack pack.json                ← NEAPs + correlation searches (+ --validate to dry-run SPL)

3. Load into ITSI
   import --pack pack.json --url ...    ← pushes via ITSI REST API

4. Verify everything is live
   probe --pack pack.json --watch       ← readiness board + rolling activity log

5. Break something (and watch ITSI react)
   degrade --pack pack.json --target otel-demo --duration 300
```

---

## Commands

**Primary (start here):**

| Command | What it does |
|---------|-------------|
| `setup` | **One command:** build pack → NEAPs → import to ITSI → probe readiness |
| `probe` | Live readiness board — health scores, KPI flow, entities, activity log, scenario status |
| `degrade` | Inject a failure scenario (otel-demo flags / k8s / HEC) with auto-recovery |

**Build your own pack (advanced):**

| Command | Mode | What it does |
|---------|------|-------------|
| `diagram` | **AI + Vision** | Analyze an architecture diagram image → full ITSI content pack |
| `apm` | **AI** | Pull live Splunk O11y service map → classify topology → ITSI pack |
| `discover` | **AI** | Plain-English architecture description → full ITSI content pack |
| `enrich` | **AI** | Claude reviews a pack, fills coverage gaps, scores 0–100 |
| `neap` | **AI + Template** | Generate NEAPs (template) + correlation searches (AI); optional `--validate` |
| `cmdb` | Template + opt. AI | Parse SNOW CMDB export → service tree |
| `bootstrap` | Template | Demo-ready pack from a pre-built vertical |
| `kpi-discover` | Template | Show recommended KPIs for a service type |
| `preflight` | **Live check** | Verify Splunk has indexed data ready for ITSI onboarding |
| `import` | **Live push** | Push a content pack into live ITSI via REST API |

---

## AI Provider

The tool auto-detects which AI backend to use — no code changes or flags needed.

### Option 1: Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

### Option 2: AWS Bedrock

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

# Or a named profile / IAM role — no env vars needed
export AWS_PROFILE=my-profile
```

Default Bedrock model: `us.anthropic.claude-3-5-sonnet-20241022-v2:0`

```bash
export BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
export ITSI_AI_PROVIDER=bedrock     # force Bedrock
export ITSI_AI_PROVIDER=anthropic   # force Anthropic API
```

**Auto-detection order:** `ITSI_AI_PROVIDER` env var → `ANTHROPIC_API_KEY` present → AWS Bedrock fallback

---

## Primary Commands

### `setup` — one command to rule them all

The fastest path from zero to a live ITSI demo. Chains all four steps automatically.

```bash
# Full setup
python -m itsi_accelerator setup \
  --vertical otel-demo \
  --url https://my-show.splunkcloud.com \
  --token $SPLUNK_TOKEN

# Build pack only (no ITSI instance yet)
python -m itsi_accelerator setup --vertical otel-demo --no-import
```

```
Step 1/4  Bootstrap   Build content pack from vertical template  (no AI)
Step 2/4  NEAPs       Generate NEAPs + correlation searches       (Claude)
Step 3/4  Import      Push pack to ITSI via REST API
Step 4/4  Probe       Readiness check → verdict + next steps
```

Skip steps with `--no-neap` or `--no-import`. Pack is always saved to disk (`<vertical>_pack.json`
by default, or `--save-pack <path>`). Steps 3–4 are skipped automatically if no `--url` is given.

---

## Content Pack Commands

### `diagram` — architecture diagram to ITSI pack

The most demo-worthy entry point. Claude reads an architecture diagram visually and generates
the full service tree — no typing, no CMDB, just hand it the picture.

Supported formats: **PNG, JPEG, GIF, WEBP, SVG**

```bash
python -m itsi_accelerator diagram \
  --image architecture.png \
  --context "healthcare SaaS, 99.9% SLA on patient portal" \
  --output arch_pack.json
```

Claude infers services, call-path dependencies, CI types, and monitoring tiers directly from
the diagram. SVG is sent as XML text; raster formats use Claude's vision API.

---

### `apm` — live O11y service map to ITSI pack

Pulls the real service topology from Splunk Observability Cloud APM and converts it to an
ITSI content pack. No guessing — the services, dependencies, and call patterns are real.

```bash
python -m itsi_accelerator apm \
  --token $SPLUNK_ACCESS_TOKEN \
  --realm us1 \
  --environment prod \
  --output prod_pack.json
```

**What it does:**
1. Calls `GET /v2/apm/v1/service-map` for the live topology (nodes + edges)
2. Sends the topology to Claude to classify CI types and monitoring tiers
3. Generates KPIs per service using the same AI pipeline as `discover`
4. Auto-creates entity objects for each service

AppDynamics source (`--source appd`) is on the roadmap.

---

### `discover` — plain English to full content pack

```bash
python -m itsi_accelerator discover \
  --description "Java Spring Boot microservices on K8s: payments API, fraud scoring,
    PostgreSQL, Redis, Kafka. 99.9% SLA on payments." \
  --context "FSI / banking, PCI-DSS required" \
  --output banking_pack.json \
  --index prod
```

Claude generates a hierarchical service model (business → app → platform → infra), infers
CI types, flags SLA-critical services, generates 4–6 custom KPIs per service with real SPL,
and surfaces monitoring coverage gaps.

---

### `enrich` — AI review and gap-fill of any existing pack

```bash
python -m itsi_accelerator enrich --pack banking_pack.json --output banking_enriched.json
# Or just get a written review:
python -m itsi_accelerator enrich --pack banking_pack.json --review-only
```

Claude scores the pack 0–100, fills coverage gaps, adds missing services, and improves
under-specified KPIs. Uses a two-step pipeline (assessment → per-service KPI generation)
for reliable structured output at any pack size.

---

### `cmdb` — ServiceNow CMDB export to service tree

```bash
python -m itsi_accelerator cmdb \
  --input cmdb_export.csv \
  --output itsi_pack.json \
  --title "Acme Banking Platform" \
  --ai-infer   # optional: Claude infers CI types for unclassified CIs
```

Supports CSV and JSON CMDB exports. Auto-detects column aliases (`sys_class_name`, `ci_class`,
`type`, etc.). Maps SNOW CI classes to KPI templates. `--ai-infer` lets Claude classify CIs
from name + description when `sys_class_name` is missing or generic.

---

### `bootstrap` — vertical templates (no AI)

```bash
python -m itsi_accelerator bootstrap --vertical banking --output demo.json
```

| Vertical | Business service | Services | Use case |
|----------|-----------------|----------|----------|
| `otel-demo` | Astronomy Shop | 15 (astroshop) | OTel Demo app — hardcoded, no AI call |
| `banking` | Retail Banking Platform | 11 | FSI banking demos |
| `healthcare` | Patient Care Platform | 11 | Healthcare / payer demos |
| `retail` | E-Commerce Platform | 12 | Retail / CPG demos |
| `telecom` | Subscriber Platform | 11 | Telco / cable demos |
| `manufacturing` | Smart Factory Platform | 10 | Industrial / OT demos |
| `generic` | 3-Tier Web Application | 9 | Generic demo / PoV |

---

## Episode Management

### `neap` — generate NEAPs + correlation searches

Adds the episode management layer on top of any content pack. NEAPs are built from templates
(no AI call, no runtime dependency) — one per service with configurable silence break. Correlation
searches are AI-generated SPL that fire notables into those episodes.

```bash
python -m itsi_accelerator neap \
  --pack apm_pack.json \
  --index prod \
  --output apm_neap_bundle.json
```

Output is a separate JSON bundle (NEAPs + correlation searches) loaded via the ITSI REST API or
packaged into a Splunk app alongside the content pack.

```bash
# NEAPs only, skip AI correlation search generation:
python -m itsi_accelerator neap --pack pack.json --no-correlation-searches

# Dry-run each SPL against a live Splunk instance — flags zero-result searches:
python -m itsi_accelerator neap --pack pack.json \
  --validate \
  --validate-url https://my-show.splunkcloud.com \
  --validate-token $SPLUNK_TOKEN
```

`--validate` runs each generated SPL via `/services/search/jobs/export` and prints a result count
per search. Zero-result searches are flagged as warnings — the most common cause is an index name
mismatch. Edit the SPL in the bundle JSON before loading into ITSI.

**Design note:** NEAPs are intentionally template-based — the pattern is predictable and
encoding it into the framework removes the AI dependency at runtime.

---

## Demo Operations

### `degrade` — inject failure scenarios

For the OTel Demo vertical, all 5 astroshop feature-flag scenarios are **hardcoded** — no AI call,
no pack file needed. For custom packs, Claude generates scenarios from your services + KPIs.

```bash
# OTel Demo — hardcoded scenarios, instant, no AI:
python -m itsi_accelerator degrade --vertical otel-demo --target otel-demo

# Run a specific scenario (substring match on name):
python -m itsi_accelerator degrade \
  --vertical otel-demo --target otel-demo \
  --scenario payment --duration 120

# Custom pack — Claude generates scenarios:
python -m itsi_accelerator degrade --pack pack.json --target otel-demo
```

**Hardcoded OTel Demo scenarios (no AI, no pack needed):**

| Scenario | Feature flag | Alert in |
|----------|-------------|----------|
| Payment Service Failure | `paymentServiceFailure` | ~60s |
| Recommendation Cache Failure | `recommendationServiceCacheFailure` | ~90s |
| Cart Service Failure | `cartServiceFailure` | ~45s |
| Product Catalog Error | `productCatalogServiceError` | ~60s |
| Shipping Service Failure | `shippingServiceFailure` | ~45s |

**Targets:**

| Target | How it works |
|--------|-------------|
| `simulate` | Dry-run — prints commands and talking points, touches nothing (default) |
| `otel-demo` | Toggles OpenTelemetry Demo feature flags (cleanest for astroshop) |
| `k8s` | Executes `kubectl` scale/delete/exec commands against your cluster |
| `hec` | Sends synthetic events to Splunk HEC to trigger correlation searches |

Each scenario includes **demo talking points** — 4–5 bullets for the SA to narrate while ITSI reacts.

---

### `probe` — live demo readiness board

Pre-demo check that verifies everything is live and working. Use `--watch` to keep it running
on a second monitor during the demo.

```bash
python -m itsi_accelerator probe \
  --url https://my-show.splunkcloud.com \
  --token $SPLUNK_TOKEN \
  --pack apm_pack.json \
  --watch
```

`--watch` shows a split display: readiness board on top, rolling activity log on the bottom
(queries `itsi_tracked_alerts` every 15s — notables fired, health changes in real time).

**What it checks:**

| Check | Pass condition |
|-------|---------------|
| Connectivity | Splunk auth succeeds |
| Services exist | All pack services found in ITSI |
| Health scores | Every service has an active health score |
| KPI data flow | `itsi_summary` index has data in the last 15m |
| Entities | Entities present and linked to pack services |
| Correlation searches | All generated searches enabled |
| KPI backfill | All backfill jobs complete |
| Active scenario | Shows scenario name + countdown if `degrade` is running |

**Example output (`--watch`):**
```
╭─ ITSI Demo Readiness [otel_demo_pack.json]  READY ─────────╮
│  ✓  Connectivity          Splunk 9.1.2                      │
│  ✓  Services exist        All 15 services present           │
│  ✓  Health scores         All 15 services have scores       │
│  ✓  KPI data flow         68 KPIs computing (last 15m)      │
│  ✓  Entities              15 entities (15 linked)           │
│  ✓  Correlation searches  12 searches enabled               │
│  ·  KPI backfill          Not available on this version     │
│  !  Active scenario       ACTIVE: 'Payment Service Failure' │
│                           1m 43s until auto-recovery        │
╰─ Score: 93%  |  Checked: 14:32:05  |  Refreshing every 30s ╯
╭─ Activity Log (itsi_tracked_alerts, last 5m) ───────────────╮
│  14:31:52  CRIT [Payment Service] payment errors spiking    │
│  14:31:47  HIGH [Checkout Service] downstream dependency    │
│  14:30:12  INFO [K8s Cluster] pod restart detected          │
╰────────────────────────────────────────────────────────────╯
```

The probe and degrade commands share a local state file (`~/.itsi_accelerator_state.json`) —
the moment `degrade` injects a failure, `probe --watch` immediately flips to `CAUTION` and
shows the countdown.

---

## Infrastructure Commands

### `preflight` — data readiness check (pre-onboarding)

```bash
python -m itsi_accelerator preflight \
  --url https://splunk.example.com:8089 \
  --token $SPLUNK_TOKEN
```

Checks: connectivity, metric indexes present, host entities discoverable,
recognized sourcetypes, data freshness. Returns a 0–100 readiness score.
Use this *before* onboarding a customer — `probe` is for *after* deployment.

---

### `import` — push into live ITSI

```bash
python -m itsi_accelerator import \
  --pack itsi_pack.json \
  --url https://splunk.example.com:8089 \
  --token $SPLUNK_TOKEN
```

Or import via the ITSI UI: **Configuration → Data Integrations → Content Library → Import**

---

## Content Pack Format

Generated packs follow the ITSI content pack schema and import cleanly via
`POST /servicesNS/nobody/SA-ITOA/itsi/content_packs/import`.

Each pack includes:
- **Services** — title, description, entity rules, dependency wiring, tags
- **KPIs** — SPL, metric name, unit, aggregation method, threshold suggestions
- **Entities** — auto-generated from each service's entity rules (linked to service key)
- **ServiceHealthScore** — auto-added to every service
- **Parent-child dependencies** — wired from CMDB, APM topology, or AI-discovered call paths

The NEAP bundle (NEAPs + correlation searches) is a separate file loaded via
`POST /servicesNS/nobody/SA-ITOA/itsi/notable_event_aggregation_policy` and the saved searches API.

---

## How the AI Works

Every AI command uses Claude's [tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
capability to produce schema-validated structured output — not free-text that needs parsing.

```
Input                         Claude pipeline                        Output
─────────────────────────     ─────────────────────────────────      ──────────────────────
Architecture diagram       ─► Vision analysis → service tree     ─► Services + deps + CI types
APM service map            ─► Topology classification            ─► ITSI-annotated service tree
Plain-English description  ─► Service tree discovery             ─► Same structured output
                           ─► KPI generation (per service)       ─► 4–6 KPIs w/ real SPL each
Existing content pack      ─► Coverage assessment                ─► Score + gap list
                           ─► Per-service KPI gap fill           ─► Improved pack
Services + KPI names       ─► Correlation search generation      ─► Batched SPL searches
Services + CI types        ─► Scenario generation                ─► inject/recover cmds + talking pts
```

**Design direction:** AI is used to discover patterns; those patterns get encoded as templates
over time, removing the runtime AI dependency. NEAPs are already template-based. OTel Demo
degradation scenarios are now hardcoded — `degrade --vertical otel-demo` makes zero AI calls.

---

## Project Structure

```
itsi-field-accelerator/
├── itsi_accelerator/
│   ├── ai/
│   │   ├── claude_client.py               # Provider auto-detection (Anthropic + Bedrock)
│   │   ├── service_discoverer.py          # Architecture → service tree; APM topology classifier
│   │   ├── kpi_generator.py               # Service context → custom KPIs with SPL
│   │   ├── diagram_analyzer.py            # Vision-based diagram → service tree
│   │   ├── correlation_search_generator.py # Batched corr search SPL generation
│   │   ├── scenario_generator.py          # Demo degradation scenario plans (AI path)
│   │   ├── pack_enricher.py               # Two-step coverage assessment + gap-fill
│   │   └── cmdb_enricher.py               # Infer CI types for unclassified CIs
│   ├── apm/
│   │   └── splunk_o11y.py                 # O11y APM REST client (service-map API)
│   ├── probe/
│   │   └── checker.py                     # ITSI readiness checks (8 checks, scored)
│   ├── degrade/
│   │   └── executor.py                    # inject → wait → recover; writes scenario state file
│   ├── templates/
│   │   ├── kpi_library.py                 # 40+ KPI templates, 11 service types
│   │   ├── verticals.py                   # 7 pre-built verticals (incl. otel-demo)
│   │   ├── neap_templates.py              # Template-based NEAP builder (no AI)
│   │   └── scenarios.py                   # Hardcoded degrade scenarios by vertical (otel-demo)
│   ├── cmdb/parser.py                     # SNOW CSV/JSON → ContentPack
│   ├── preflight/checker.py               # Splunk data readiness (5 checks, scored)
│   ├── cli/main.py                        # All 13 CLI commands (click + rich)
│   └── core/
│       ├── models.py                      # Service, KPI, Entity, CorrelationSearch, NEAP, ContentPack
│       └── importer.py                    # ITSI REST API importer
└── examples/sample_cmdb_export.csv
```

---

## Relationship to ITSI 5.0.3 AI Discovery

| Capability | ITSI 5.0.3 AI Discovery | This tool |
|------------|------------------------|-----------|
| Works on-premises | Phase 2/3 (TBD) | **Now** |
| CMDB as primary input (ServiceNow) | Phase 3 (TBD) | **Now** |
| Works without indexed data | No | **Yes** (`discover`, `diagram`, `bootstrap`) |
| From architecture diagram | No | **Yes** (`diagram`) |
| From live APM topology | No | **Yes** (`apm`) |
| AI-generated SPL | Yes (from indexed data) | **Yes** (from description + context) |
| AWS Bedrock as AI backend | No | **Yes** |
| Entities auto-generated | Yes | **Yes** |
| NEAP + correlation search generation | No | **Yes** (`neap`, also via `setup`) |
| Demo degradation scenarios | No | **Yes** (`degrade` — hardcoded for otel-demo) |
| Demo readiness board + activity log | No | **Yes** (`probe --watch`) |
| One-command end-to-end setup | No | **Yes** (`setup`) |
| Coverage scoring | No | **Yes** (0–100) |
| Pack gap analysis + enrichment | No | **Yes** (`enrich`) |

---

## Contributing

**Adding a new service type (template path):**
1. Add entries to `KPI_TEMPLATES` in `itsi_accelerator/templates/kpi_library.py`
2. Add CI class aliases to `CI_CLASS_ALIASES`
3. Optionally add the service type to a vertical in `verticals.py`

**Adding a new vertical:**
Add an entry to `VERTICALS` in `itsi_accelerator/templates/verticals.py` following the existing
pattern (list of CI dicts with `name`, `ci_class`, `parent`, `business_service`).

**Adding a new APM source:**
Implement the client in `itsi_accelerator/apm/<source>.py` with a `get_service_map()` method
returning `{"nodes": [...], "edges": [...]}`. Wire it into the `apm` CLI command.

---

*Built by Marc Bui — Splunk Solutions Architect*
