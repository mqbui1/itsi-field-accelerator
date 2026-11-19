"""Generate ITSI Field Accelerator demo & team testing guide as a .docx."""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ── Splunk brand colours ───────────────────────────────────────────────────────
SPLUNK_BLACK  = RGBColor(0x1A, 0x1A, 0x1A)
SPLUNK_GREEN  = RGBColor(0x65, 0xA6, 0x37)
SPLUNK_GREY   = RGBColor(0x55, 0x55, 0x55)
SPLUNK_DGREY  = RGBColor(0x33, 0x33, 0x33)
SPLUNK_LGREY  = RGBColor(0xF4, 0xF4, 0xF4)
WHITE         = RGBColor(0xFF, 0xFF, 0xFF)
TABLE_HEADER  = RGBColor(0x1A, 0x1A, 0x1A)
TABLE_ALT     = RGBColor(0xF9, 0xF9, 0xF9)
AMBER         = RGBColor(0xE8, 0x8A, 0x00)


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


def add_body(doc, text, bold=False, colour=None, space_after=4, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(10.5)
    run.font.color.rgb = colour or SPLUNK_BLACK
    return p


def add_bullet(doc, text, bold_prefix=None, colour=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = colour or SPLUNK_BLACK
        rest = p.add_run(text)
        rest.font.size = Pt(10.5)
        rest.font.color.rgb = SPLUNK_BLACK
    else:
        r = p.add_run(text)
        r.font.size = Pt(10.5)
        r.font.color.rgb = colour or SPLUNK_BLACK
    return p


def add_code_block(doc, lines):
    """Render a list of strings as a monospace code block."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent  = Inches(0.3)
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(8)
    for i, line in enumerate(lines):
        r = p.add_run(line)
        r.font.name  = "Courier New"
        r.font.size  = Pt(8.5)
        r.font.color.rgb = SPLUNK_DGREY
        if i < len(lines) - 1:
            p.add_run("\n")


def add_callout(doc, label, text, colour=None):
    """Bold label + body on the same paragraph, indented."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.25)
    p.paragraph_format.space_after = Pt(4)
    rl = p.add_run(f"{label}  ")
    rl.bold = True
    rl.font.size = Pt(10.5)
    rl.font.color.rgb = colour or SPLUNK_GREEN
    rb = p.add_run(text)
    rb.font.size = Pt(10.5)
    rb.font.color.rgb = SPLUNK_BLACK
    return p


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
        for j, (cell, txt) in enumerate(zip(row.cells, row_data)):
            cell.width = col_widths[j]
            set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            r = p.add_run(txt)
            r.font.size = Pt(10)
            r.font.color.rgb = SPLUNK_BLACK
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after  = Pt(3)


def add_dialog_line(doc, speaker, text, is_claude=False):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_after = Pt(3)
    rs = p.add_run(f"{speaker}  ")
    rs.bold = True
    rs.font.name = "Courier New"
    rs.font.size = Pt(8.5)
    rs.font.color.rgb = SPLUNK_GREEN if is_claude else SPLUNK_DGREY
    rt = p.add_run(text)
    rt.font.name = "Courier New"
    rt.font.size = Pt(8.5)
    rt.font.color.rgb = SPLUNK_DGREY


def main():
    doc = Document()

    for section in doc.sections:
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    # ── Title ─────────────────────────────────────────────────────────────────
    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(2)
    r = title.add_run("ITSI Field Accelerator")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = SPLUNK_BLACK

    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(14)
    rs = sub.add_run("Demo & Team Testing Guide  ·  Marc Bui, Solutions Architect")
    rs.font.size = Pt(10.5)
    rs.font.color.rgb = SPLUNK_GREY

    add_divider(doc)

    # ── Intro ─────────────────────────────────────────────────────────────────
    add_body(doc,
        "This guide walks through the recommended progression for demoing or testing the "
        "ITSI Field Accelerator with your team — from zero-friction baseline to full AI-driven "
        "service discovery on a real customer scenario.",
        colour=SPLUNK_GREY, space_after=0)

    add_divider(doc)

    # ── Round 1 ───────────────────────────────────────────────────────────────
    add_heading(doc, "Round 1 — Everyone tries it (no API key needed)")
    add_body(doc,
        "Goal: establish a baseline. Show the concept works, get the team familiar with the "
        "output format. No credentials required.",
        colour=SPLUNK_GREY, space_after=8)

    add_heading(doc, "Setup", level=2)
    add_code_block(doc, [
        "git clone https://github.com/mqbui1/itsi-field-accelerator.git",
        "cd itsi-field-accelerator",
        "pip install -r requirements.txt --index-url https://pypi.org/simple/",
    ])

    add_heading(doc, "Run bootstrap + enrich", level=2)
    add_code_block(doc, [
        "# Step 1 — instant template pack (no AI, no key):",
        "python -m itsi_accelerator bootstrap --vertical banking --output demo.json",
        "",
        "# Step 2 — Claude reviews and fills gaps (requires API key or AWS creds):",
        "python -m itsi_accelerator enrich --pack demo.json --output demo_enriched.json",
    ])

    add_body(doc,
        "Open demo.json and walk through the structure — services, KPI SPL, dependencies. "
        "Then open demo_enriched.json and compare. The delta (coverage score, specific SPL "
        "Claude added vs. the generic template SPL) is where the conversation starts.",
        space_after=0)

    add_divider(doc)

    # ── Round 2 ───────────────────────────────────────────────────────────────
    add_heading(doc, "Round 2 — The real demo (use a customer scenario)")
    add_body(doc,
        "This is the \"wow\" moment. Use a real customer architecture your team has recently "
        "worked on. The more specific the description, the more impressive the output.",
        colour=SPLUNK_GREY, space_after=8)

    add_heading(doc, "Example: FSI banking (high specificity)", level=2)
    add_code_block(doc, [
        "python -m itsi_accelerator discover \\",
        "  --description \"Oracle FLEXCUBE core banking on WebLogic, fronted by an Apigee",
        "    API gateway. Mobile banking via React Native hitting a Node.js BFF. Fraud",
        "    scoring is a Python ML service calling out to a Pega decisioning engine.",
        "    PostgreSQL for accounts, Kafka for transaction events, Redis session cache.",
        "    PCI-DSS scope. 99.95% SLA on card auth.\" \\",
        "  --context \"FSI / retail banking\" \\",
        "  --output customer_pack.json",
    ])

    add_heading(doc, "What to highlight as it runs", level=2)
    add_bullet(doc,
        " — Apigee → api_gateway, Python ML → fraud_detection, Pega → other with a note",
        bold_prefix="Service types Claude infers")
    add_bullet(doc,
        " — not index=main sourcetype=*, but WebLogic JMX metrics, Kafka consumer lag, Apigee response codes",
        bold_prefix="The SPL it writes")
    add_bullet(doc,
        " — PCI-DSS audit log gaps, missing synthetic monitoring for the SLA, no APM source for the BFF",
        bold_prefix="Coverage gaps flagged")

    doc.add_paragraph()
    add_body(doc,
        "The closing question that sells it: \"How long would it take you to write these 14 service "
        "definitions, wire the dependencies, and author 70 KPI searches by hand?\" The answer is "
        "usually 2–3 weeks minimum.",
        colour=SPLUNK_GREY, italic=True, space_after=0)

    add_divider(doc)

    # ── Round 3 ───────────────────────────────────────────────────────────────
    add_heading(doc, "Round 3 — Claude Code skill (if the team uses Claude Code)")
    add_body(doc,
        "The skill removes the need to know the CLI at all — just describe what you need "
        "in plain English and Claude handles the rest.",
        colour=SPLUNK_GREY, space_after=10)

    add_heading(doc, "Example conversation", level=2)
    add_dialog_line(doc, "You:",
        "Generate an ITSI content pack for a FSI customer. Java Spring Boot on\n"
        "        Kubernetes, PostgreSQL, Redis, Kafka. 99.9% SLA on the payments service.")
    add_dialog_line(doc, "Claude:",
        "Running discover mode...\n"
        "        [checks prerequisites, confirms Anthropic API provider]\n"
        "        [runs: python3 -m itsi_accelerator discover --description \"...\" --context \"FSI\" ...]\n\n"
        "        Done. 14 services → banking_pack.json\n"
        "        Coverage gaps flagged:\n"
        "          • No APM/distributed tracing source mentioned\n"
        "          • No synthetic monitoring for SLA validation\n\n"
        "        Next: enrich it to fill the gaps, or import it into ITSI?",
        is_claude=True)
    add_dialog_line(doc, "You:", "Enrich it.")
    add_dialog_line(doc, "Claude:",
        "Coverage score: 81/100 (was 54/100)\n"
        "        Added 18 KPIs across 4 services. 2 new services added.\n"
        "        Remaining gaps: synthetic monitoring, Kafka JMX source",
        is_claude=True)

    add_divider(doc)

    # ── Prerequisites table ───────────────────────────────────────────────────
    add_heading(doc, "Who needs what")
    build_simple_table(doc,
        headers=["Team member", "Needs"],
        rows=[
            ("Testing bootstrap / enrich on a template pack",
             "Nothing — just Python + the repo cloned"),
            ("Testing AI modes (discover, enrich from scratch)",
             "Anthropic API key (ANTHROPIC_API_KEY) or AWS Bedrock credentials"),
            ("Testing the Claude Code skill",
             "Claude Code + splunk-observability-toolkit loaded in session"),
        ],
        col_widths=[Inches(2.8), Inches(3.4)],
    )
    doc.add_paragraph()

    add_divider(doc)

    # ── Vertical cheat sheet ──────────────────────────────────────────────────
    add_heading(doc, "Best first scenario by vertical")
    build_simple_table(doc,
        headers=["Your focus", "Start here", "Then try discover with..."],
        rows=[
            ("FSI / Banking",   "bootstrap --vertical banking",
             "Payments, fraud detection, core banking, Kafka, PCI-DSS scope"),
            ("Healthcare",      "bootstrap --vertical healthcare",
             "HL7 interfaces, Epic EHR, claims processing, HIPAA compliance"),
            ("Retail / CPG",    "bootstrap --vertical retail",
             "Microservices storefront, inventory, payment gateway, fraud"),
            ("Telco / Cable",   "bootstrap --vertical telecom",
             "BSS/OSS stack, billing engine, subscriber DB, provisioning"),
            ("Manufacturing",   "bootstrap --vertical manufacturing",
             "MES, ERP integration, SCADA bus, OT/IT boundary"),
            ("Generic / PoV",   "bootstrap --vertical generic",
             "Any 3-tier web app — web, API, app, DB, cache, message bus"),
        ],
        col_widths=[Inches(1.3), Inches(2.0), Inches(2.9)],
    )
    doc.add_paragraph()

    add_divider(doc)

    # ── Session agenda ────────────────────────────────────────────────────────
    add_heading(doc, "Suggested team session agenda (~45 min)")
    build_simple_table(doc,
        headers=["Time", "Activity"],
        rows=[
            ("5 min",  "Context: blank canvas problem, 4–12 week TTV, what ITSI 5.0.3 covers vs. doesn't"),
            ("10 min", "Bootstrap + enrich on template pack — everyone runs it, establish the baseline"),
            ("15 min", "Live discover on a real customer description — walk through output together"),
            ("10 min", "Claude Code skill demo (if applicable)"),
            ("10 min", "\"What would make this better?\" — collect feedback on missing CI types, verticals, SPL patterns"),
        ],
        col_widths=[Inches(0.9), Inches(5.3)],
    )
    doc.add_paragraph()

    add_body(doc,
        "The last 10 minutes is the most valuable. The team will immediately start naming customer "
        "scenarios and edge cases — that becomes the prioritized backlog for the next iteration.",
        colour=SPLUNK_GREY, italic=True, space_after=0)

    add_divider(doc)

    # ── What to watch for ─────────────────────────────────────────────────────
    add_heading(doc, "What to watch for during the team test")

    add_bullet(doc,
        " — Claude's SPL is good but won't match every customer's exact sourcetypes. "
        "Note which KPIs need tweaking — this feeds back into KPI template improvements.",
        bold_prefix="SPL accuracy")
    add_bullet(doc,
        " — Claude may map unusual CI names to the wrong type. Run cmdb --ai-infer "
        "on a real export and check the confidence scores.",
        bold_prefix="CI type inference")
    add_bullet(doc,
        " — Run preflight against a real Splunk instance to see which checks pass/fail "
        "before importing a pack.",
        bold_prefix="Data readiness")
    add_bullet(doc,
        " — If a team member has a live ITSI instance available, do the full end-to-end: "
        "discover → enrich → import → verify in the ITSI UI.",
        bold_prefix="End-to-end import")

    add_divider(doc)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = doc.add_paragraph()
    footer.paragraph_format.space_before = Pt(6)
    footer.paragraph_format.space_after  = Pt(2)
    rf = footer.add_run("Repo: ")
    rf.bold = True
    rf.font.size = Pt(10.5)
    rf.font.color.rgb = SPLUNK_BLACK
    rl = footer.add_run("github.com/mqbui1/itsi-field-accelerator")
    rl.font.size = Pt(10.5)
    rl.font.color.rgb = SPLUNK_GREEN

    out = "ITSI_Field_Accelerator_Demo_Guide.docx"
    doc.save(out)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
