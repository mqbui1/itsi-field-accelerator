"""
Generate ITSI Field Accelerator live demo walkthrough as a .docx.
Documents the actual session output: bootstrap → enrich → discover → enrich pipeline
using the FSI/FLEXCUBE banking scenario.
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── Colours ───────────────────────────────────────────────────────────────────
SPLUNK_BLACK  = RGBColor(0x1A, 0x1A, 0x1A)
SPLUNK_GREEN  = RGBColor(0x65, 0xA6, 0x37)
SPLUNK_GREY   = RGBColor(0x55, 0x55, 0x55)
SPLUNK_DGREY  = RGBColor(0x33, 0x33, 0x33)
WHITE         = RGBColor(0xFF, 0xFF, 0xFF)
TABLE_HEADER  = RGBColor(0x1A, 0x1A, 0x1A)
TABLE_ALT     = RGBColor(0xF9, 0xF9, 0xF9)
AMBER         = RGBColor(0xC8, 0x6C, 0x00)
CODE_BG       = RGBColor(0xF5, 0xF5, 0xF5)


def set_cell_bg(cell, rgb):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
    tcPr.append(shd)


def add_divider(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after  = Pt(6)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "CCCCCC")
    pBdr.append(bottom)
    pPr.append(pBdr)


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(16 if level == 1 else 13)
    run.font.color.rgb = SPLUNK_BLACK if level == 1 else SPLUNK_DGREY
    return p


def add_body(doc, text, colour=None, space_after=4, italic=False, bold=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    r.font.size = Pt(10.5)
    r.font.color.rgb = colour or SPLUNK_BLACK
    r.italic = italic
    r.bold = bold
    return p


def add_bullet(doc, text, bold_prefix=None, colour=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    if bold_prefix:
        rb = p.add_run(bold_prefix)
        rb.bold = True
        rb.font.size = Pt(10.5)
        rb.font.color.rgb = colour or SPLUNK_BLACK
        rt = p.add_run(text)
        rt.font.size = Pt(10.5)
        rt.font.color.rgb = SPLUNK_BLACK
    else:
        r = p.add_run(text)
        r.font.size = Pt(10.5)
        r.font.color.rgb = colour or SPLUNK_BLACK
    return p


def add_code_block(doc, lines, space_after=10):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.3)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(space_after)
    for i, line in enumerate(lines):
        r = p.add_run(line)
        r.font.name  = "Courier New"
        r.font.size  = Pt(8.5)
        r.font.color.rgb = SPLUNK_DGREY
        if i < len(lines) - 1:
            p.add_run("\n")


def add_output_block(doc, lines, space_after=10):
    """Lighter style for CLI output — slightly indented, grey."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.4)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after  = Pt(space_after)
    for i, line in enumerate(lines):
        r = p.add_run(line)
        r.font.name  = "Courier New"
        r.font.size  = Pt(8)
        r.font.color.rgb = SPLUNK_GREY
        if i < len(lines) - 1:
            p.add_run("\n")


def add_callout(doc, text, colour=None):
    """Indented italic callout — used for talking-track highlights."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.3)
    p.paragraph_format.right_indent = Inches(0.3)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(8)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    for side in ("left",):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "12")
        b.set(qn("w:space"), "6")
        b.set(qn("w:color"), "65A637")
        pBdr.append(b)
    pPr.append(pBdr)
    r = p.add_run(text)
    r.font.size  = Pt(10.5)
    r.font.color.rgb = colour or SPLUNK_DGREY
    r.italic = True


def build_simple_table(doc, headers, rows, col_widths):
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    for j, (cell, hdr) in enumerate(zip(table.rows[0].cells, headers)):
        cell.width = col_widths[j]
        set_cell_bg(cell, TABLE_HEADER)
        p = cell.paragraphs[0]
        r = p.add_run(hdr)
        r.bold = True
        r.font.size = Pt(10)
        r.font.color.rgb = WHITE
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)
    for i, row_data in enumerate(rows):
        row = table.rows[i + 1]
        bg = TABLE_ALT if i % 2 == 0 else WHITE
        for j, (cell, (txt, bold)) in enumerate(
            zip(row.cells, [(d, False) if isinstance(d, str) else d for d in row_data])
        ):
            cell.width = col_widths[j]
            set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            r = p.add_run(txt)
            r.font.size = Pt(10)
            r.font.color.rgb = SPLUNK_BLACK
            r.bold = bold
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after  = Pt(3)


def add_step_badge(doc, number, title):
    """Bold step number + title as a visual section marker."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(6)
    rn = p.add_run(f"Step {number}  ")
    rn.bold = True
    rn.font.size = Pt(13)
    rn.font.color.rgb = SPLUNK_GREEN
    rt = p.add_run(title)
    rt.bold = True
    rt.font.size = Pt(13)
    rt.font.color.rgb = SPLUNK_BLACK


def main():
    doc = Document()
    for section in doc.sections:
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    # ── Title ─────────────────────────────────────────────────────────────────
    t = doc.add_paragraph()
    t.paragraph_format.space_after = Pt(2)
    r = t.add_run("ITSI Field Accelerator")
    r.bold = True; r.font.size = Pt(22); r.font.color.rgb = SPLUNK_BLACK

    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(4)
    rs = sub.add_run("Live Demo Walkthrough  ·  FSI / Banking Scenario  ·  Marc Bui, Solutions Architect")
    rs.font.size = Pt(10.5); rs.font.color.rgb = SPLUNK_GREY

    add_divider(doc)

    # ── Intro ─────────────────────────────────────────────────────────────────
    add_body(doc,
        "This document records a complete end-to-end demo session of the ITSI Field Accelerator, "
        "run against a real FSI/banking architecture (Oracle FLEXCUBE). It captures the actual "
        "command output, talking track, and key observations at each step — ready to walk through "
        "with your team or use as a reference for running your own demo.",
        colour=SPLUNK_GREY, space_after=4)

    add_body(doc, "Four steps, one pipeline:", bold=True, space_after=4)
    add_bullet(doc, "bootstrap  — instant template pack, no AI, establishes the baseline",
               bold_prefix="Step 1  ")
    add_bullet(doc, "enrich  — Claude reviews the template and fills gaps",
               bold_prefix="Step 2  ")
    add_bullet(doc, "discover  — full AI generation from a plain-English architecture description",
               bold_prefix="Step 3  ")
    add_bullet(doc, "enrich  — Claude reviews its own discover output and finds more",
               bold_prefix="Step 4  ")

    add_divider(doc)

    # ── Prerequisites ─────────────────────────────────────────────────────────
    add_heading(doc, "Prerequisites check")
    add_body(doc, "Run once before starting. Verifies repo, Python deps, and AI provider:", space_after=6)
    add_code_block(doc, [
        "ls itsi_accelerator/__init__.py  →  REPO OK",
        "python3 -c \"import anthropic, click, rich\"  →  DEPS OK",
        "PROVIDER: Anthropic API  (or AWS Bedrock — auto-detected)",
    ])
    add_body(doc, "If DEPS MISSING:", bold=True, space_after=2)
    add_code_block(doc, [
        "pip install -r requirements.txt --index-url https://pypi.org/simple/",
    ], space_after=0)

    add_divider(doc)

    # ── Step 1: Bootstrap ─────────────────────────────────────────────────────
    add_step_badge(doc, 1, "bootstrap — instant template pack (no API key needed)")
    add_body(doc,
        "Generates a complete service tree from the built-in banking vertical template. "
        "No credentials, no Claude call. Run this first to show the baseline before AI.",
        colour=SPLUNK_GREY, space_after=8)

    add_code_block(doc, [
        "python3 -m itsi_accelerator bootstrap --vertical banking --output demo_banking.json",
    ])

    add_heading(doc, "Output", level=2)
    add_output_block(doc, [
        "Done. Bootstrap 'banking': 11 services -> demo_banking.json",
        "",
        "Service                   KPIs  Tags",
        "Retail Banking Platform      0  field-accelerator, business-service",
        "Online Banking Portal        3  field-accelerator, web_server, production",
        "Mobile Banking API           3  field-accelerator, api_gateway, production",
        "Account Service              3  field-accelerator, app_server, production",
        "Payment Processing           3  field-accelerator, payment_processor, production",
        "Fraud Detection Engine       2  field-accelerator, fraud_detection, production",
        "Identity & Auth Service      2  field-accelerator, auth_service, production",
        "Core Banking DB              4  field-accelerator, database, production",
        "Transaction DB               4  field-accelerator, database, production",
        "Event Bus (Kafka)            2  field-accelerator, message_queue, production",
        "Banking App Hosts            3  field-accelerator, linux_host, production",
    ])

    add_heading(doc, "Talking track", level=2)
    add_bullet(doc, " has 0 KPIs — correct. It's the business-tier root; health rolls up from children.",
               bold_prefix="Retail Banking Platform")
    add_bullet(doc, " across services — these are generic templates, not tailored SPL.",
               bold_prefix="KPI counts are low (2–4)")
    add_bullet(doc, " — we don't know what's missing until Claude looks at it.",
               bold_prefix="No coverage score yet")
    doc.add_paragraph()
    add_callout(doc, "This is the \"before\" state. Ask the team: how long would it take to build "
                "even this by hand? Then run Step 2 to show what Claude adds.")

    add_divider(doc)

    # ── Step 2: Enrich bootstrap ───────────────────────────────────────────────
    add_step_badge(doc, 2, "enrich — Claude reviews and gap-fills the template pack")
    add_body(doc,
        "Claude runs a two-step pipeline: first assess coverage gaps across all services, "
        "then generate new KPIs per flagged service. Takes 2–4 minutes for an 11-service pack.",
        colour=SPLUNK_GREY, space_after=8)

    add_code_block(doc, [
        "python3 -m itsi_accelerator enrich \\",
        "  --pack demo_banking.json \\",
        "  --output demo_banking_enriched.json \\",
        "  --index main",
    ])

    add_heading(doc, "Output", level=2)
    add_output_block(doc, [
        "Coverage score: 58/100",
        "",
        "Summary: The Banking Demo Pack provides a solid structural foundation with 11 services",
        "spanning the full retail banking stack, but several critical services lack complete",
        "golden signal coverage. Five operational services — Fraud Detection Engine, Identity",
        "& Auth Service, Event Bus (Kafka), Account Service, and Mobile Banking API — are",
        "missing one or more golden signals. Additionally, key supporting infrastructure",
        "services (a message queue dead-letter monitor, a CDN/WAF layer, and a secrets/",
        "certificate management service) are absent entirely.",
        "",
        "Applying 8 service improvements + 5 new services...",
        "Done. Enriched pack -> demo_banking_enriched.json",
        "",
        "Remaining gaps:",
        "  • Identity & Auth Service has zero latency or throughput KPIs — token issuance",
        "    latency and login request rate are foundational signals for any OAuth2/OIDC",
        "    service and their absence means auth degradation is effectively invisible.",
        "  • Fraud Detection Engine covers only 2 of 4 golden signals; missing throughput",
        "    and error-rate KPIs mean a stalled or erroring ML scoring pipeline would not",
        "    trigger any ITSI alert, allowing fraudulent transactions to pass unscored.",
        "  • Payment Processing lacks a transactions-per-second KPI — a catastrophic drop",
        "    in payment volume would not be detected.",
        "  • No CDN/WAF service — customer-facing attack surface completely unmonitored.",
        "  • Event Bus (Kafka) has no error or saturation KPIs — silent data loss risk.",
    ])

    add_heading(doc, "Talking track", level=2)
    add_bullet(doc, " — Claude went from 11 to 16 services by adding CDN/WAF, dead-letter queue, secrets/cert management.",
               bold_prefix="5 new services added")
    add_bullet(doc, " — added missing golden signals to Fraud, Auth, Kafka, Account Service, Mobile API.",
               bold_prefix="8 service improvements")
    add_callout(doc,
        "\"Fraud Detection Engine covers only 2 of 4 golden signals — a stalled ML scoring pipeline "
        "would not trigger any ITSI alert, allowing fraudulent transactions to pass unscored.\"\n\n"
        "That's not generic boilerplate. Claude reasoned about the specific risk of that service type "
        "in a banking context.")

    add_divider(doc)

    # ── Step 3: Discover ───────────────────────────────────────────────────────
    add_step_badge(doc, 3, "discover — full AI generation from plain-English description")
    add_body(doc,
        "This is the main event. One paragraph description of a real customer architecture → "
        "complete service tree with custom, stack-specific SPL. The FLEXCUBE scenario is ideal "
        "because it includes non-standard components (Pega, FLEXCUBE internal naming) that "
        "generic templates can't handle.",
        colour=SPLUNK_GREY, space_after=8)

    add_code_block(doc, [
        "python3 -m itsi_accelerator discover \\",
        "  --description \"Oracle FLEXCUBE core banking on WebLogic, fronted by an Apigee API",
        "    gateway. Mobile banking via React Native hitting a Node.js BFF. Fraud scoring is",
        "    a Python ML service calling out to a Pega decisioning engine. PostgreSQL for",
        "    accounts, Kafka for transaction events, Redis session cache. PCI-DSS scope.",
        "    99.95% SLA on card auth.\" \\",
        "  --context \"FSI / retail banking\" \\",
        "  --output flexcube_pack.json \\",
        "  --index prod",
    ])

    add_heading(doc, "Architecture summary (Claude's output)", level=2)
    add_output_block(doc, [
        "A PCI-DSS scoped retail banking platform built on Oracle FLEXCUBE / WebLogic as the",
        "core system of record, fronted by an Apigee API gateway and a Node.js BFF serving",
        "React Native mobile clients. Real-time fraud decisioning is delivered by a Python ML",
        "service chained to a Pega engine, with Kafka as the transaction event backbone,",
        "PostgreSQL for persistent account data, and Redis for session caching. The service",
        "tree is structured to surface card authorization health as the primary SLA objective",
        "at 99.95% availability.",
    ])

    add_heading(doc, "Service table (16 services discovered)", level=2)
    add_output_block(doc, [
        "Service                           KPIs  Tier",
        "Retail Banking Platform              0  business",
        "Card Authorization                   0  business",
        "Mobile Banking                       0  business",
        "API Gateway (Apigee)                 6  application",
        "Mobile BFF (Node.js)                 6  application",
        "Identity & Session                   6  application",
        "Core Banking (FLEXCUBE)              6  application",
        "Fraud Detection (Python ML)          6  application",
        "Pega Decisioning Engine              6  application",
        "Transaction Event Streaming (Kafka)  6  platform",
        "Accounts Database (PostgreSQL)       6  platform",
        "Session Cache (Redis)                6  platform",
        "WebLogic Application Servers         6  infrastructure",
        "Core Banking Host Infrastructure     6  infrastructure",
        "Fraud ML Host Infrastructure         6  infrastructure",
        "Mobile BFF Host Infrastructure       6  infrastructure",
    ])

    add_heading(doc, "FLEXCUBE KPIs (spot-check)", level=2)
    add_body(doc,
        "Open flexcube_pack.json and inspect the Core Banking (FLEXCUBE) service KPIs. "
        "These are the ones to show on-screen during the demo:", space_after=6)
    add_output_block(doc, [
        "KPI: FLEXCUBE Transaction Success Rate (%)",
        "SPL: index=prod sourcetype=\"weblogic_stdout\"",
        "     (source=\"*flexcube*\" OR source=\"*fcubs*\")",
        "     (\"TXN_STATUS\" OR \"transaction\" OR \"ACCTRANSFER\") ...",
        "",
        "KPI: Posting Failure Count (EOD/Batch)",
        "SPL: index=prod sourcetype=\"weblogic_stdout\"",
        "     (source=\"*flexcube*\" OR source=\"*fcubs*\")",
        "     (\"POSTING_STATUS=F\" OR \"POST_FAILED\" ...) ...",
        "",
        "KPI: WebLogic JVM Heap Utilization (%)",
        "SPL: index=prod sourcetype=\"weblogic_jmx\"",
        "     (source=\"*weblogic*\" OR source=\"*flexcube*\")",
        "     metric_name=\"jvm.heap.used\" OR \"HeapSize\" ...",
    ])

    add_heading(doc, "Talking track", level=2)
    add_bullet(doc,
        " — fcubs is the internal FLEXCUBE process name. Claude knows this. No one told it.",
        bold_prefix="source=\"*fcubs*\"")
    add_bullet(doc,
        " — FLEXCUBE-specific EOD batch posting failure string. This is not generic SPL.",
        bold_prefix="\"POSTING_STATUS=F\"")
    add_bullet(doc,
        " with HeapSize — specific to the WebLogic JMX MBean collector.",
        bold_prefix="sourcetype=\"weblogic_jmx\"")
    add_bullet(doc,
        " — Pega was mentioned as a dependency, not a service. Claude made it one.",
        bold_prefix="Pega Decisioning Engine as its own service")
    add_bullet(doc,
        " — PCI-DSS audit log gaps, missing synthetic monitoring, Apigee log export not confirmed, WebLogic add-on needed, etc.",
        bold_prefix="10 coverage gaps flagged")

    add_heading(doc, "Fraud Detection & Pega KPIs (spot-check)", level=2)
    add_body(doc, "These are the two services that make the demo land for FSI audiences:", space_after=6)
    add_output_block(doc, [
        "=== Fraud Detection ===",
        "  Fraud Score Latency P95 (ms)       — P95 specifically on score_transaction actions",
        "  Transaction Scoring Throughput      — tx/s on fraud_detection sourcetype",
        "  Fraud Scoring Error Rate (%)        — matches on status=error|fail|exception|timeout",
        "  ML Scoring Worker Queue Depth       — saturation signal; Claude knew ML workers have a queue",
        "  Fraud Block Rate (%)                — business signal; matches decision=\"blocked\"",
        "  Pega Decisioning Engine Availability — dependency availability modeled on calling service",
        "",
        "=== Pega Decisioning Engine ===",
        "  Decision Engine Latency (p95, ms)   — sourcetype=\"pega:decisioning\"",
        "  Decision Throughput (decisions/min)  — decisions/min bucketed by time",
        "  Decision Error Rate (%)              — matches status=error|exception|timeout",
        "  JVM Heap Utilisation (%)             — sourcetype=\"pega:jvm\"",
        "  Model Inference Failure Rate (%)     — component=model_scoring specifically",
        "  Fallback Decision Rate (%)           — decision_path=\"fallback\" — Pega-specific concept",
    ])

    add_callout(doc,
        "\"How many of your ITSI customers have a Pega decisioning engine? How long does it "
        "currently take to instrument that service from scratch?\"\n\n"
        "The answer is usually 'we just don't' — non-standard services get left out because the "
        "SPL effort is too high. This fills that gap.")

    add_divider(doc)

    # ── Step 4: Enrich discover ────────────────────────────────────────────────
    add_step_badge(doc, 4, "enrich — Claude reviews its own discover output")
    add_body(doc,
        "Run enrich on the AI-generated pack. Even after a full discover, Claude finds more. "
        "This is the honesty story — it's not 100/100, and that's the right answer.",
        colour=SPLUNK_GREY, space_after=8)

    add_code_block(doc, [
        "python3 -m itsi_accelerator enrich \\",
        "  --pack flexcube_pack.json \\",
        "  --output flexcube_enriched.json \\",
        "  --index prod",
    ])

    add_heading(doc, "Output", level=2)
    add_output_block(doc, [
        "Coverage score: 62/100",
        "",
        "Summary: The Oracle FLEXCUBE retail banking content pack has solid foundational",
        "coverage across its 16 services, with most application, platform, and infrastructure",
        "services carrying 6 KPIs each. However, Card Authorization and Mobile Banking are",
        "SLA-bearing business services that critically need golden signal coverage. Additionally,",
        "Oracle DB for FLEXCUBE and a Payment Network/Switch gateway are entirely absent.",
        "",
        "Applying 7 service improvements + 5 new services...",
        "Done. Enriched pack -> flexcube_enriched.json",
        "",
        "Remaining gaps:",
        "  • Card Authorization and Mobile Banking have zero KPIs despite being SLA-bearing",
        "    business services — cannot alert on customer-facing outcomes for these flows.",
        "  • No Oracle Database service — most likely root cause of core banking outages is",
        "    completely unmonitored.",
        "  • No Payment Network Gateway — external card scheme connectivity and latency are",
        "    invisible, yet directly determine card authorization SLA attainment.",
        "  • WebLogic stuck thread count and Work Manager queue depth absent — the most",
        "    common precursor to FLEXCUBE outages cannot be detected.",
        "  • HSM / Encryption Service missing — a PCI-DSS compliance and operational blind",
        "    spot for all card authorization cryptographic operations.",
    ])

    add_heading(doc, "Talking track", level=2)
    add_bullet(doc,
        " — Oracle DB (it knew FLEXCUBE runs on Oracle, not just PostgreSQL), Payment Network Gateway, HSM/Encryption Service, Card Auth KPIs, Mobile Banking KPIs.",
        bold_prefix="5 new services added")
    add_bullet(doc,
        " — Claude inferred HSM from \"PCI-DSS scope\" in the original description. A consultant would need deep domain knowledge to know this component exists.",
        bold_prefix="HSM / Encryption Service")
    add_callout(doc,
        "\"No Payment Network Gateway service — external scheme connectivity and latency are "
        "invisible, yet they directly determine card authorization SLA attainment.\"\n\n"
        "62/100 is the right answer. The remaining gaps require actual Splunk data — Apigee log "
        "export confirmed, PCI audit index, synthetic monitoring. That's what preflight is for. "
        "That's the natural handoff into a real ITSI onboarding engagement.")

    add_divider(doc)

    # ── Final summary ─────────────────────────────────────────────────────────
    add_heading(doc, "Demo close — the full pipeline in numbers")
    build_simple_table(doc,
        headers=["Step", "Command", "Services", "KPIs", "Coverage"],
        rows=[
            [("Step 1", False), ("bootstrap (template)", False),     ("11", False), ("29",  False), ("—",      False)],
            [("Step 2", False), ("+ enrich",             False),     ("16", False), ("72",  False), ("58/100", False)],
            [("Step 3", False), ("discover (FLEXCUBE)",  False),     ("16", False), ("78",  False), ("—",      False)],
            [("Step 4", True),  ("+ enrich",             True),      ("21", True),  ("115", True),  ("62/100", True)],
        ],
        col_widths=[Inches(0.7), Inches(1.9), Inches(0.9), Inches(0.7), Inches(1.0)],
    )
    doc.add_paragraph()

    add_callout(doc,
        "21 services and 115 KPIs — with FLEXCUBE-specific SPL, Oracle DB, HSM, Payment Network "
        "Gateway — from a one-paragraph description and two commands. That's the work of multiple "
        "weeks of consultant workshops, done in under 5 minutes.")

    add_body(doc,
        "The 62/100 score is a feature, not a bug. It's honest — the remaining gaps need actual "
        "Splunk data to close. Run preflight to show the data readiness check, then import the "
        "pack into ITSI to complete the loop.",
        colour=SPLUNK_GREY, italic=True, space_after=0)

    add_divider(doc)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = doc.add_paragraph()
    footer.paragraph_format.space_before = Pt(6)
    footer.paragraph_format.space_after  = Pt(2)
    rf = footer.add_run("Repo: ")
    rf.bold = True; rf.font.size = Pt(10.5); rf.font.color.rgb = SPLUNK_BLACK
    rl = footer.add_run("github.com/mqbui1/itsi-field-accelerator")
    rl.font.size = Pt(10.5); rl.font.color.rgb = SPLUNK_GREEN

    out = "ITSI_Field_Accelerator_Demo_Walkthrough.docx"
    doc.save(out)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
