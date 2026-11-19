"""Generate ITSI Field Accelerator team summary as a .docx."""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

# ── Splunk brand colours ───────────────────────────────────────────────────────
SPLUNK_BLACK   = RGBColor(0x1A, 0x1A, 0x1A)
SPLUNK_GREEN   = RGBColor(0x65, 0xA6, 0x37)   # Splunk green
SPLUNK_GREY    = RGBColor(0x55, 0x55, 0x55)
SPLUNK_LGREY   = RGBColor(0xF4, 0xF4, 0xF4)
SPLUNK_DGREY   = RGBColor(0x33, 0x33, 0x33)
WHITE          = RGBColor(0xFF, 0xFF, 0xFF)
TABLE_HEADER   = RGBColor(0x1A, 0x1A, 0x1A)   # near-black header rows
TABLE_ALT      = RGBColor(0xF9, 0xF9, 0xF9)


def set_cell_bg(cell, rgb: RGBColor):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}")
    tcPr.append(shd)


def set_cell_border(cell, **edges):
    """edges: top/bottom/left/right = (size_pt, color_hex)"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge, (sz, color) in edges.items():
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(sz * 8))
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), color)
        tcBorders.append(b)
    tcPr.append(tcBorders)


def add_heading(doc, text, level=1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(16 if level == 1 else 13)
    run.font.color.rgb = SPLUNK_BLACK if level == 1 else SPLUNK_DGREY
    return p


def add_body(doc, text, bold=False, colour=None, space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(10.5)
    run.font.color.rgb = colour or SPLUNK_BLACK
    return p


def add_bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    if bold_prefix:
        r = p.add_run(bold_prefix)
        r.bold = True
        r.font.size = Pt(10.5)
        r.font.color.rgb = SPLUNK_BLACK
        rest = p.add_run(text)
        rest.font.size = Pt(10.5)
        rest.font.color.rgb = SPLUNK_BLACK
    else:
        r = p.add_run(text)
        r.font.size = Pt(10.5)
        r.font.color.rgb = SPLUNK_BLACK
    return p


def add_code(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.3)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.font.name = "Courier New"
    run.font.size = Pt(9)
    run.font.color.rgb = SPLUNK_DGREY


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


def build_modes_table(doc):
    """Four-row modes table."""
    table = doc.add_table(rows=5, cols=3)
    table.style = "Table Grid"
    table.autofit = False

    col_widths = [Inches(1.1), Inches(1.9), Inches(3.2)]
    for i, row in enumerate(table.rows):
        for j, cell in enumerate(row.cells):
            cell.width = col_widths[j]

    headers = ["Mode", "Input", "What Claude does"]
    header_row = table.rows[0]
    for j, (cell, hdr) in enumerate(zip(header_row.cells, headers)):
        set_cell_bg(cell, TABLE_HEADER)
        p = cell.paragraphs[0]
        run = p.add_run(hdr)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = WHITE
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)

    rows_data = [
        ("discover",  "Plain-English architecture description",
         "Generates full service tree, infers service types, writes custom KPIs with real SPL, wires parent-child dependencies"),
        ("enrich",    "Existing content pack (JSON)",
         "Reviews golden signal coverage, fills gaps, adds missing services, scores overall coverage 0–100"),
        ("cmdb",      "ServiceNow CMDB CSV/JSON export",
         "Maps CI classes to KPI templates; --ai-infer flag lets Claude classify generic/unknown CIs"),
        ("bootstrap", "Vertical name (banking, healthcare, retail, etc.)",
         "Generates a demo-ready pack from curated templates — no data or CMDB needed"),
    ]

    for i, (mode, inp, desc) in enumerate(rows_data):
        row = table.rows[i + 1]
        bg = TABLE_ALT if i % 2 == 0 else WHITE

        # Mode cell — green monospace
        set_cell_bg(row.cells[0], bg)
        p0 = row.cells[0].paragraphs[0]
        r0 = p0.add_run(mode)
        r0.bold = True
        r0.font.name = "Courier New"
        r0.font.size  = Pt(9.5)
        r0.font.color.rgb = SPLUNK_GREEN

        for cell, txt in [(row.cells[1], inp), (row.cells[2], desc)]:
            set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            r = p.add_run(txt)
            r.font.size = Pt(10)
            r.font.color.rgb = SPLUNK_BLACK
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after  = Pt(3)


def build_skill_table(doc):
    """6-row skill automation table."""
    table = doc.add_table(rows=7, cols=2)
    table.style = "Table Grid"
    table.autofit = False

    col_widths = [Inches(1.8), Inches(4.4)]
    for row in table.rows:
        for j, cell in enumerate(row.cells):
            cell.width = col_widths[j]

    headers = ["Step", "What happens automatically"]
    header_row = table.rows[0]
    for cell, hdr in zip(header_row.cells, headers):
        set_cell_bg(cell, TABLE_HEADER)
        p = cell.paragraphs[0]
        run = p.add_run(hdr)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = WHITE
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)

    rows_data = [
        ("Prerequisites",        "Checks repo is cloned, Python deps installed, and which AI provider is available. Installs missing deps."),
        ("Mode detection",       "Infers discover / enrich / cmdb / bootstrap from your message. Asks once if ambiguous."),
        ("Conversational intake","Collects only the inputs needed for that mode. Sensible defaults for everything optional."),
        ("Runs the CLI",         "Executes python3 -m itsi_accelerator <mode> with your inputs."),
        ("Surfaces results",     "Shows the service table, coverage score, and flagged gaps inline in the conversation."),
        ("Follow-up",            "Offers enrich → import → preflight as next steps without leaving the conversation."),
    ]

    for i, (step, desc) in enumerate(rows_data):
        row = table.rows[i + 1]
        bg = TABLE_ALT if i % 2 == 0 else WHITE

        set_cell_bg(row.cells[0], bg)
        p0 = row.cells[0].paragraphs[0]
        r0 = p0.add_run(step)
        r0.bold = True
        r0.font.size = Pt(10)
        r0.font.color.rgb = SPLUNK_DGREY
        p0.paragraph_format.space_before = Pt(3)
        p0.paragraph_format.space_after  = Pt(3)

        set_cell_bg(row.cells[1], bg)
        p1 = row.cells[1].paragraphs[0]
        r1 = p1.add_run(desc)
        r1.font.size = Pt(10)
        r1.font.color.rgb = SPLUNK_BLACK
        p1.paragraph_format.space_before = Pt(3)
        p1.paragraph_format.space_after  = Pt(3)


def build_comparison_table(doc):
    """6-row comparison table."""
    table = doc.add_table(rows=7, cols=3)
    table.style = "Table Grid"
    table.autofit = False

    col_widths = [Inches(2.6), Inches(1.7), Inches(1.9)]
    for row in table.rows:
        for j, cell in enumerate(row.cells):
            cell.width = col_widths[j]

    headers = ["Scenario", "ITSI 5.0.3 AI Discovery", "This tool"]
    header_row = table.rows[0]
    for cell, hdr in zip(header_row.cells, headers):
        set_cell_bg(cell, TABLE_HEADER)
        p = cell.paragraphs[0]
        run = p.add_run(hdr)
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = WHITE
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after  = Pt(3)

    rows_data = [
        ("Cloud deployment, data already indexed",  "Yes",                    "Optional"),
        ("On-premises ITSI",                        "Not yet (Phase 2/3 TBD)","Now"),
        ("CMDB as primary input (ServiceNow)",      "Not yet (Phase 3 TBD)",  "Now"),
        ("Pre-data / no indexed data yet",          "No",                     "Yes"),
        ("PoV / demo environment",                  "No",                     "Yes"),
        ("Gap analysis on existing pack",           "No",                     "Yes"),
    ]

    for i, (scenario, itsi, tool) in enumerate(rows_data):
        row = table.rows[i + 1]
        bg = TABLE_ALT if i % 2 == 0 else WHITE
        for cell, txt in zip(row.cells, [scenario, itsi, tool]):
            set_cell_bg(cell, bg)
            p = cell.paragraphs[0]
            r = p.add_run(txt)
            r.font.size = Pt(10)
            r.font.color.rgb = SPLUNK_BLACK
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after  = Pt(3)


def main():
    doc = Document()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Inches(0.9)
        section.bottom_margin = Inches(0.9)
        section.left_margin   = Inches(1.0)
        section.right_margin  = Inches(1.0)

    # ── Title block ──────────────────────────────────────────────────────────
    title = doc.add_paragraph()
    title.paragraph_format.space_after = Pt(2)
    r = title.add_run("ITSI Field Accelerator")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = SPLUNK_BLACK

    sub = doc.add_paragraph()
    sub.paragraph_format.space_after = Pt(14)
    rs = sub.add_run("Team Summary  ·  Marc Bui, Solutions Architect")
    rs.font.size = Pt(10.5)
    rs.font.color.rgb = SPLUNK_GREY

    add_divider(doc)

    # ── Problem ──────────────────────────────────────────────────────────────
    add_heading(doc, "What problem does it solve?")
    add_body(doc,
        "Standing up Splunk ITSI has always had a \"blank canvas\" problem. "
        "Before a customer sees meaningful service health, they need:",
        space_after=6)

    add_bullet(doc, " to decompose their architecture into a service model", bold_prefix="2–4 consultant workshops")
    add_bullet(doc, " to write KPI searches (SPL) for each service type", bold_prefix="Deep Splunk expertise")
    add_bullet(doc, " to wire ServiceNow CIs to ITSI services", bold_prefix="Manual CMDB mapping")
    add_bullet(doc, " before alert quality is usable", bold_prefix="Weeks of threshold tuning")

    doc.add_paragraph()
    add_body(doc,
        "Result: 4–12 weeks before a customer sees value. This is a confirmed churn risk — "
        "internal Confluence (the product team's own docs) calls it \"Blank Canvas Paralysis.\"",
        space_after=6)

    add_body(doc,
        "Splunk shipped AI-driven service discovery in ITSI 5.0.3, but it's Cloud-only, "
        "requires data already indexed, and CMDB-first workflows (ServiceNow → service tree) "
        "are on the roadmap with no committed date.",
        colour=SPLUNK_GREY, space_after=0)

    add_divider(doc)

    # ── What was built ───────────────────────────────────────────────────────
    add_heading(doc, "What was built")
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    r1 = p.add_run("itsi-field-accelerator")
    r1.bold = True
    r1.font.name = "Courier New"
    r1.font.size  = Pt(10.5)
    r1.font.color.rgb = SPLUNK_GREEN
    r2 = p.add_run(
        " — a CLI tool that collapses weeks of ITSI onboarding prep into minutes using Claude AI. "
        "It covers the gap between \"customer has ITSI licensed\" and \"customer has a working service model.\""
    )
    r2.font.size = Pt(10.5)
    r2.font.color.rgb = SPLUNK_BLACK

    add_heading(doc, "Four modes of input → one output: a ready-to-import ITSI content pack", level=2)
    doc.add_paragraph()
    build_modes_table(doc)
    doc.add_paragraph()

    add_heading(doc, "What comes out", level=2)
    add_body(doc, "A content pack that imports directly into ITSI via UI or REST API, containing:", space_after=6)
    add_bullet(doc, "Services with correct monitoring tiers (business → application → platform → infrastructure)")
    add_bullet(doc, "4–6 KPIs per service with real, runnable SPL tailored to each service type")
    add_bullet(doc, "Parent-child dependency wiring")
    add_bullet(doc, "Coverage gap report flagging what's missing (data sources, compliance blind spots, etc.)")
    add_bullet(doc, "Coverage score (0–100) so the customer knows what they're starting with")

    add_divider(doc)

    # ── Why this matters ─────────────────────────────────────────────────────
    add_heading(doc, "Why this matters for field teams")

    add_bullet(doc,
        " generates a demo-ready pack in seconds for any vertical "
        "(banking, healthcare, retail, telecom, manufacturing). No prep work. "
        "Walk in with a live ITSI service model already loaded.",
        bold_prefix="For SAs running PoVs: bootstrap")

    add_bullet(doc,
        " turns a 30-minute architecture conversation into a complete first draft — "
        "services, KPIs, SPL — that would otherwise take 2–3 weeks of workshops.",
        bold_prefix="For customers doing onboarding: discover")

    add_bullet(doc,
        " parses their SNOW export and builds the service tree automatically. "
        "--ai-infer handles the common case where sys_class_name is blank or generic.",
        bold_prefix="For CMDB-first customers (ServiceNow shops): cmdb")

    add_bullet(doc,
        " reviews what they have, identifies golden signal gaps, and fills them — "
        "without the customer having to know what they're missing.",
        bold_prefix="For customers already on ITSI: enrich")

    add_divider(doc)

    # ── Comparison ───────────────────────────────────────────────────────────
    add_heading(doc, "Relationship to ITSI 5.0.3 AI Discovery")
    add_body(doc, "This is complementary, not competitive:", space_after=8)
    build_comparison_table(doc)
    doc.add_paragraph()

    add_divider(doc)

    # ── Claude Code Skill ─────────────────────────────────────────────────────
    add_heading(doc, "Claude Code Skill — invoke conversationally")
    add_body(doc,
        "If your team uses Claude Code, the tool ships with a companion skill that lets you "
        "generate ITSI content packs conversationally — no terminal switching, no flags to remember. "
        "Just describe what you need in plain English.",
        space_after=10)

    add_heading(doc, "Trigger it by saying things like:", level=2)

    convo_lines = [
        '"generate an ITSI content pack for a healthcare platform on Kubernetes"',
        '"enrich my existing banking pack and fill the coverage gaps"',
        '"bootstrap an ITSI demo for a retail customer — no API key needed"',
        '"help me onboard a new ITSI customer — they have a ServiceNow CMDB export"',
    ]
    for line in convo_lines:
        add_bullet(doc, line)

    doc.add_paragraph()
    add_heading(doc, "What the skill handles automatically", level=2)
    doc.add_paragraph()
    build_skill_table(doc)
    doc.add_paragraph()

    add_heading(doc, "Example conversation", level=2)

    dialog_lines = [
        ("You:", "Generate an ITSI content pack for a FSI customer. Java Spring Boot on Kubernetes,\n"
                 "        PostgreSQL, Redis, Kafka. 99.9% SLA on the payments service."),
        ("Claude:", "Running discover mode...\n"
                    "        [checks prerequisites, confirms Anthropic API provider]\n"
                    "        [runs: python3 -m itsi_accelerator discover --description \"...\" --context \"FSI\" ...]\n\n"
                    "        Done. 14 services → banking_pack.json\n"
                    "        Coverage gaps flagged:\n"
                    "          • No APM/distributed tracing source mentioned\n"
                    "          • No synthetic monitoring for SLA validation\n\n"
                    "        Next: enrich it to fill the gaps, or import it into ITSI?"),
        ("You:", "Enrich it."),
        ("Claude:", "Coverage score: 81/100 (was 54/100)\n"
                    "        Added 18 KPIs across 4 services. 2 new services added.\n"
                    "        Remaining gaps: synthetic monitoring, Kafka JMX source"),
    ]

    for speaker, text in dialog_lines:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(3)
        rs = p.add_run(f"{speaker}  ")
        rs.bold = True
        rs.font.name = "Courier New"
        rs.font.size = Pt(8.5)
        rs.font.color.rgb = SPLUNK_GREEN if speaker == "Claude:" else SPLUNK_DGREY
        rt = p.add_run(text)
        rt.font.name = "Courier New"
        rt.font.size = Pt(8.5)
        rt.font.color.rgb = SPLUNK_DGREY

    doc.add_paragraph()
    add_body(doc,
        "The skill lives in the splunk-observability-toolkit under skills/itsi-accelerator/. "
        "Works with both Anthropic API and AWS Bedrock — auto-detected from your environment.",
        colour=SPLUNK_GREY, space_after=0)

    add_divider(doc)

    # ── How to try it ────────────────────────────────────────────────────────
    add_heading(doc, "How to try it")

    code_lines = [
        "git clone https://github.com/mqbui1/itsi-field-accelerator.git",
        "cd itsi-field-accelerator",
        "pip install -r requirements.txt",
        "",
        "# Quickest demo — no data or API key needed:",
        "python -m itsi_accelerator bootstrap --vertical banking --output demo.json",
        "",
        "# AI mode — Anthropic API key or AWS Bedrock credentials:",
        "python -m itsi_accelerator discover \\",
        '  --description "Java microservices on K8s: payments API, fraud scoring, PostgreSQL, Redis, Kafka. 99.9% SLA." \\',
        "  --context \"FSI / banking\" \\",
        "  --output banking_pack.json",
    ]

    code_block = doc.add_paragraph()
    code_block.paragraph_format.left_indent = Inches(0.3)
    code_block.paragraph_format.space_after = Pt(8)
    for i, line in enumerate(code_lines):
        r = code_block.add_run(line)
        r.font.name = "Courier New"
        r.font.size = Pt(8.5)
        r.font.color.rgb = SPLUNK_DGREY
        if i < len(code_lines) - 1:
            code_block.add_run("\n")

    add_body(doc,
        "The bootstrap command works without any API key. The AI commands (discover, enrich, cmdb --ai-infer) "
        "require either an Anthropic API key (ANTHROPIC_API_KEY) or AWS Bedrock credentials — "
        "the tool auto-detects which one to use.",
        colour=SPLUNK_GREY, space_after=12)

    # ── Repo footer ──────────────────────────────────────────────────────────
    add_divider(doc)
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

    note = doc.add_paragraph()
    rn = note.add_run(
        "Happy to walk the team through a live demo — the discover command on a real customer architecture "
        "is the fastest way to see the value."
    )
    rn.font.size = Pt(10.5)
    rn.font.color.rgb = SPLUNK_GREY
    rn.italic = True

    out = "ITSI_Field_Accelerator_Team_Summary.docx"
    doc.save(out)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
