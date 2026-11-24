"""CLI entry point for the ITSI Field Accelerator."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()


@click.group()
@click.version_option("0.3.0")
def cli():
    """ITSI Field Accelerator — fast-track ITSI demo setup and degradation testing.

    \b
    QUICK START (OTel Demo):
      setup    One command: build pack → NEAPs → import → probe
      degrade  Inject a failure scenario during the demo
      probe    Live readiness board (use --watch)

    \b
    ADVANCED (build your own pack):
      bootstrap / cmdb / apm / diagram / discover → build a pack
      neap                                        → add NEAPs + correlation searches
      import                                      → push pack to ITSI
    """
    pass


# ── cmdb ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--input", "-i", required=True, help="CMDB export file (CSV or JSON)")
@click.option("--output", "-o", default="itsi_content_pack.json", show_default=True)
@click.option("--title", "-t", default="CMDB Import", show_default=True)
@click.option("--index", default="main", show_default=True, help="Splunk index for KPI searches")
@click.option("--ai-infer", is_flag=True, default=False, help="Use Claude to infer CI types for unclassified CIs")
def cmdb(input, output, title, index, ai_infer):
    """Generate ITSI service tree from a ServiceNow CMDB export (CSV or JSON)."""
    from itsi_accelerator.cmdb.parser import CMDBParser

    console.print(f"[bold cyan]Parsing CMDB export:[/] {input}")
    parser = CMDBParser(index=index)
    rows = parser.parse(input)

    if ai_infer:
        from itsi_accelerator.ai.cmdb_enricher import infer_ci_types
        console.print(f"[dim]Inferring CI types for unclassified CIs via Claude...[/]")
        rows = infer_ci_types(rows)
        inferred = sum(1 for r in rows if r.get("_ci_type_inferred"))
        if inferred:
            console.print(f"[green]Claude inferred types for {inferred} CIs[/]")

    pack = parser.build_content_pack(rows, pack_title=title)
    Path(output).write_text(json.dumps(pack.to_dict(), indent=2))

    console.print(f"[bold green]Done.[/] {len(pack.services)} services -> {output}")
    _print_service_table(pack)


# ── setup (meta-command: bootstrap → neap → import → probe) ──────────────────

@cli.command()
@click.option("--vertical", "-v", required=True,
              help="Vertical template to use: otel-demo, banking, healthcare, retail, telecom, manufacturing, generic")
@click.option("--url", "-u", default="", envvar="SPLUNK_URL",
              help="Splunk/ITSI base URL (env: SPLUNK_URL). Omit to skip import + probe.")
@click.option("--token", "-t", default="", envvar="SPLUNK_TOKEN",
              help="Splunk auth token (env: SPLUNK_TOKEN). Required for import + probe.")
@click.option("--index", default="main", show_default=True,
              help="Splunk index for KPI SPL templates")
@click.option("--save-pack", default=None,
              help="Save the generated content pack JSON to this path (default: <vertical>_pack.json)")
@click.option("--no-import", is_flag=True, default=False,
              help="Skip the ITSI import step (useful when no ITSI instance is available yet)")
@click.option("--no-neap", is_flag=True, default=False,
              help="Skip NEAP + correlation search generation")
@click.option("--no-ssl-verify", is_flag=True, default=False)
def setup(vertical, url, token, index, save_pack, no_import, no_neap, no_ssl_verify):
    """
    One command: build content pack → NEAPs → import to ITSI → probe readiness.

    The fastest path from zero to a live ITSI demo. Provide a vertical name and
    your Splunk credentials — setup handles the rest.

    \b
    Examples:
      # Full setup (OTel Demo)
      itsi-accelerator setup --vertical otel-demo \\
        --url https://my-show.splunkcloud.com --token $SPLUNK_TOKEN

      # Build pack only (no ITSI instance yet)
      itsi-accelerator setup --vertical otel-demo --no-import

      # Save pack to a specific path
      itsi-accelerator setup --vertical otel-demo \\
        --url https://my-show.splunkcloud.com --token $SPLUNK_TOKEN \\
        --save-pack ~/demo/astroshop_pack.json
    """
    import requests as req
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    from itsi_accelerator.templates.verticals import get_vertical
    from itsi_accelerator.cmdb.parser import CMDBParser
    from itsi_accelerator.core.models import Service, EntityRule, CorrelationSearch
    from itsi_accelerator.templates.neap_templates import build_neaps

    needs_itsi = not no_import and bool(url and token)

    console.print(Panel(
        f"[bold]Vertical:[/] {vertical}\n"
        f"[bold]Index:[/] {index}\n"
        f"[bold]ITSI import:[/] {'yes — ' + url if needs_itsi else '[dim]skipped[/]'}\n"
        f"[bold]NEAPs:[/] {'yes' if not no_neap else '[dim]skipped[/]'}",
        title="[bold cyan]ITSI Field Accelerator — Setup[/]",
    ))

    # ── Step 1: Bootstrap ──────────────────────────────────────────────────────
    console.print("\n[bold cyan]Step 1/4[/] [bold]Bootstrap content pack[/]")
    try:
        rows = get_vertical(vertical)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    parser = CMDBParser(index=index)
    pack = parser.build_content_pack(rows, pack_title=f"{vertical.title()} Demo Pack")
    pack_dict = pack.to_dict()

    pack_path = Path(save_pack) if save_pack else Path(f"{vertical.replace('-', '_')}_pack.json")
    pack_path.write_text(json.dumps(pack_dict, indent=2))
    console.print(f"  [green]✓[/] {len(pack.services)} services  →  {pack_path}")

    # ── Step 2: NEAPs + correlation searches ───────────────────────────────────
    neap_objects = []
    cs_objects: list[CorrelationSearch] = []
    if not no_neap:
        console.print("\n[bold cyan]Step 2/4[/] [bold]Generate NEAPs + correlation searches[/]")
        services_raw = pack_dict.get("data", {}).get("services", [])

        # Build service stubs for NEAP builder
        svc_stubs = []
        for s in services_raw:
            stub = Service(title=s["title"], description=s.get("description", ""))
            stub._key = s["_key"]
            stub.services_depends_on = s.get("services_depends_on", [])
            svc_stubs.append(stub)

        neap_objects = build_neaps(svc_stubs)
        console.print(f"  [green]✓[/] {len(neap_objects)} NEAPs (template-based)")

        # Correlation searches via Claude
        from itsi_accelerator.ai.correlation_search_generator import generate_correlation_searches
        services_summary = []
        for s in services_raw:
            kpis = [k for k in s.get("kpis", []) if k.get("title") != "ServiceHealthScore"]
            services_summary.append({
                "name": s["title"],
                "description": s.get("description", ""),
                "ci_type": _infer_ci_type_from_tags(s.get("tags", [])),
                "sla_critical": "sla-critical" in " ".join(s.get("tags", [])).lower(),
                "kpis": kpis[:4],
            })

        with console.status("  [dim]Claude is generating correlation searches...[/]"):
            cs_dicts = generate_correlation_searches(services=services_summary, index=index)

        name_to_key = {s["title"]: s["_key"] for s in services_raw}
        for cs_dict in cs_dicts:
            svc_key = name_to_key.get(cs_dict.get("service_name", ""), "")
            cs_objects.append(CorrelationSearch(
                name=cs_dict["name"],
                description=cs_dict.get("description", ""),
                search=cs_dict["search"],
                service_key=svc_key,
                severity=cs_dict.get("severity", "medium"),
                alert_title=cs_dict.get("alert_title", cs_dict["name"]),
                cron_schedule=cs_dict.get("cron_schedule", "*/5 * * * *"),
            ))
        console.print(f"  [green]✓[/] {len(cs_objects)} correlation searches")

        neap_bundle = {
            "title": pack_dict.get("title", vertical),
            "_pack_key": pack_dict.get("_key", ""),
            "correlation_searches": [cs.to_dict() for cs in cs_objects],
            "notable_event_aggregation_policies": [n.to_dict() for n in neap_objects],
        }
        neap_path = pack_path.with_name(pack_path.stem + "_neap_bundle.json")
        neap_path.write_text(json.dumps(neap_bundle, indent=2))
        console.print(f"  [green]✓[/] NEAP bundle  →  {neap_path}")
    else:
        console.print("\n[bold cyan]Step 2/4[/] [dim]NEAPs skipped (--no-neap)[/]")

    # ── Step 3: Import to ITSI ─────────────────────────────────────────────────
    if needs_itsi:
        console.print("\n[bold cyan]Step 3/4[/] [bold]Import content pack to ITSI[/]")
        session = req.Session()
        session.verify = not no_ssl_verify
        session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            resp = session.post(
                f"{url.rstrip('/')}/servicesNS/nobody/SA-ITOA/itsi/content_packs/import",
                data=json.dumps({"content_pack": pack_dict, "overwrite": False}),
                timeout=60,
            )
            resp.raise_for_status()
            console.print(f"  [green]✓[/] Content pack imported to {url}")
        except Exception as e:
            console.print(f"  [yellow]![/] Import failed: {e}")
            console.print("  [dim]You can retry with: itsi-accelerator import --pack " + str(pack_path) + " --url <url> --token <token>[/]")
    else:
        console.print("\n[bold cyan]Step 3/4[/] [dim]Import skipped (--no-import or no --url/--token)[/]")
        console.print(f"  [dim]When ready: itsi-accelerator import --pack {pack_path} --url <url> --token <token>[/]")

    # ── Step 4: Probe ──────────────────────────────────────────────────────────
    if needs_itsi:
        console.print("\n[bold cyan]Step 4/4[/] [bold]Probe ITSI readiness[/]")
        from itsi_accelerator.probe.checker import ProbeChecker
        from rich.text import Text
        import datetime

        checker = ProbeChecker(url=url, token=token, pack_dict=pack_dict, verify_ssl=not no_ssl_verify)
        with console.status("  [dim]Checking ITSI...[/]"):
            report = checker.run()

        for check in report.checks:
            icon = Text(check.icon, style=check.color)
            console.print(Text.assemble("  ", icon, " ", Text(check.name + ": ", style="bold"), check.message))

        verdict_style = f"bold white on {report.verdict_color}"
        console.print(f"\n  Score: {report.score}%  Verdict: ", end="")
        console.print(Text(f" {report.verdict} ", style=verdict_style))

        if report.verdict == "READY":
            console.print(f"\n[bold green]Setup complete.[/] Your demo is ready.")
            console.print(f"  [dim]Monitor with:[/] itsi-accelerator probe --url {url} --token <token> --pack {pack_path} --watch")
            console.print(f"  [dim]Break things:[/] itsi-accelerator degrade --vertical {vertical} --target otel-demo")
        else:
            console.print(f"\n[yellow]Setup complete — but probe shows issues.[/] Check the results above.")
            console.print(f"  [dim]Re-check with:[/] itsi-accelerator probe --url {url} --token <token> --pack {pack_path}")
    else:
        console.print("\n[bold cyan]Step 4/4[/] [dim]Probe skipped (no --url/--token)[/]")
        console.print(f"\n[bold green]Pack ready.[/] Next steps:")
        console.print(f"  1. Import:   itsi-accelerator import --pack {pack_path} --url <url> --token <token>")
        console.print(f"  2. Verify:   itsi-accelerator probe  --url <url> --token <token> --pack {pack_path} --watch")
        console.print(f"  3. Demo:     itsi-accelerator degrade --vertical {vertical} --target otel-demo")


# ── bootstrap ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--vertical", "-v", required=True, help="Vertical: banking, healthcare, retail, telecom, manufacturing, otel-demo, generic")
@click.option("--output", "-o", default="demo_content_pack.json", show_default=True)
@click.option("--index", default="main", show_default=True)
def bootstrap(vertical, output, index):
    """Generate a demo-ready ITSI content pack for a given vertical."""
    from itsi_accelerator.templates.verticals import get_vertical, list_verticals
    from itsi_accelerator.cmdb.parser import CMDBParser

    try:
        rows = get_vertical(vertical)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        sys.exit(1)

    parser = CMDBParser(index=index)
    pack = parser.build_content_pack(rows, pack_title=f"{vertical.title()} Demo Pack")
    Path(output).write_text(json.dumps(pack.to_dict(), indent=2))

    console.print(f"[bold green]Done.[/] Bootstrap '{vertical}': {len(pack.services)} services -> {output}")
    _print_service_table(pack)


# ── discover (AI) ─────────────────────────────────────────────────────────────

@cli.command()
@click.option("--description", "-d", required=True, help="Plain-English architecture description")
@click.option("--context", "-c", default="", help="Additional context (industry, compliance, SLA requirements)")
@click.option("--output", "-o", default="discovered_pack.json", show_default=True)
@click.option("--index", default="main", show_default=True, help="Splunk index for generated KPI SPL")
@click.option("--ai-kpis/--template-kpis", default=True, show_default=True,
              help="Generate KPIs with Claude (ai-kpis) or use curated templates (template-kpis)")
def discover(description, context, output, index, ai_kpis):
    """
    AI-driven: describe your architecture in plain English, get a full ITSI content pack.

    Example:
      python -m itsi_accelerator discover \\
        -d "Java Spring Boot app on K8s, PostgreSQL, Redis cache, Kafka. Handles insurance claims. 99.9% SLA." \\
        -o claims_pack.json
    """
    from itsi_accelerator.ai.service_discoverer import discover_services

    console.print(Panel(
        f"[bold]Discovering service tree...[/]\n[dim]{description[:120]}{'...' if len(description) > 120 else ''}[/]",
        title="[cyan]Claude AI Discovery[/]",
    ))

    with console.status("[cyan]Analyzing architecture...[/]"):
        discovery = discover_services(description, context=context)

    summary = discovery.get("architecture_summary", "")
    if summary:
        console.print(f"\n[bold]Architecture:[/] {summary}")

    pack = _build_pack_from_discovery(
        discovery=discovery,
        title=f"AI Discovery: {description[:50]}...",
        index=index,
        ai_kpis=ai_kpis,
        context=context,
    )

    Path(output).write_text(json.dumps(pack.to_dict(), indent=2))
    console.print(f"\n[bold green]Done.[/] {len(pack.services)} services -> [cyan]{output}[/]")
    _print_service_table(pack)

    gaps = discovery.get("coverage_gaps", [])
    if gaps:
        console.print("\n[yellow]Coverage gaps to address:[/]")
        for g in gaps:
            console.print(f"  • {g}")


# ── enrich (AI) ───────────────────────────────────────────────────────────────

@cli.command()
@click.option("--pack", "-p", required=True, help="Content pack JSON to enrich")
@click.option("--output", "-o", default=None, help="Output path (default: overwrites input)")
@click.option("--index", default="main", show_default=True)
@click.option("--review-only", is_flag=True, default=False, help="Print a review without modifying the pack")
def enrich(pack, output, index, review_only):
    """
    AI-driven: Claude reviews a content pack and fills coverage gaps, improves KPIs, adds missing services.
    """
    from itsi_accelerator.ai.pack_enricher import enrich_pack, apply_enrichment, review_pack

    pack_path = Path(pack)
    pack_dict = json.loads(pack_path.read_text())

    if review_only:
        console.print(Panel(
            f"[dim]{pack_dict.get('title', 'Unknown pack')}[/]",
            title="[cyan]Claude Pack Review[/]",
        ))
        review_pack(pack_dict)
        return

    console.print(f"[bold cyan]Enriching:[/] {pack_dict.get('title', pack)}")
    with console.status("[cyan]Claude is analyzing the pack...[/]"):
        enrichment = enrich_pack(pack_dict, index=index)

    improvements = enrichment.get("service_improvements", [])
    missing = enrichment.get("missing_services", [])
    score = enrichment.get("coverage_score", 0)

    console.print(f"\n[bold]Coverage score:[/] {score}/100")
    console.print(f"[bold]Summary:[/] {enrichment.get('summary', '')}")

    changes = sum(1 for i in improvements if i.get("action") != "no_change")
    console.print(f"\n[dim]Applying {changes} service improvements + {len(missing)} new services...[/]")

    enriched = apply_enrichment(pack_dict, enrichment, index=index)

    out_path = Path(output) if output else pack_path
    out_path.write_text(json.dumps(enriched, indent=2))

    console.print(f"[bold green]Done.[/] Enriched pack -> {out_path}")

    gaps = enrichment.get("top_gaps", [])
    if gaps:
        console.print("\n[yellow]Remaining gaps:[/]")
        for g in gaps:
            console.print(f"  • {g}")


# ── kpi-discover ──────────────────────────────────────────────────────────────

@cli.command(name="kpi-discover")
@click.option("--service-type", "-s", required=True)
@click.option("--index", default="main", show_default=True)
@click.option("--output", "-o", default=None)
@click.option("--ai", is_flag=True, default=False, help="Use Claude to generate custom KPIs instead of templates")
@click.option("--description", "-d", default="", help="Service description (used with --ai)")
def kpi_discover(service_type, index, output, ai, description):
    """Show recommended KPI templates for a service type. Use --ai for Claude-generated custom KPIs."""
    if ai:
        from itsi_accelerator.ai.kpi_generator import generate_kpis
        console.print(f"[cyan]Generating AI KPIs for {service_type}...[/]")
        with console.status("[cyan]Thinking...[/]"):
            result = generate_kpis(
                service_name=service_type,
                service_description=description or f"A {service_type} service",
                ci_type=service_type,
                index=index,
            )
        kpis = result.get("kpis", [])
        note = result.get("coverage_note", "")
    else:
        from itsi_accelerator.templates.kpi_library import get_kpis_for_service_type, render_kpi, KPI_TEMPLATES
        kpis = [render_kpi(k, index=index) for k in get_kpis_for_service_type(service_type)]
        note = ""

    table = Table(title=f"KPI Templates: {service_type}", show_lines=True)
    table.add_column("KPI Title", style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Unit")
    table.add_column("Yellow", style="yellow")
    table.add_column("Red", style="red")
    for k in kpis:
        yellow = str(k.get("threshold_yellow") or k.get("thresholds", {}).get("yellow") or "adaptive")
        red = str(k.get("threshold_red") or k.get("thresholds", {}).get("red") or "adaptive")
        table.add_row(k.get("title", ""), k.get("metric", ""), k.get("unit", ""), yellow, red)
    console.print(table)
    if note:
        console.print(f"[dim]{note}[/]")

    if output:
        Path(output).write_text(json.dumps(kpis, indent=2))
        console.print(f"Saved to [cyan]{output}[/]")


# ── probe ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--url", "-u", required=True, help="Splunk/ITSI base URL, e.g. https://my-show.splunkcloud.com")
@click.option("--token", "-t", required=True, envvar="SPLUNK_TOKEN", help="Splunk auth token (env: SPLUNK_TOKEN)")
@click.option("--pack", "-p", default=None, help="Content pack JSON to cross-reference service names (optional)")
@click.option("--output", "-o", default=None, help="Save report JSON to this path")
@click.option("--no-ssl-verify", is_flag=True, default=False)
@click.option("--watch", "-w", is_flag=True, default=False,
              help="Continuously refresh the readiness board every 30s (Ctrl+C to stop)")
@click.option("--interval", default=30, show_default=True,
              help="Refresh interval in seconds (used with --watch)")
def probe(url, token, pack, output, no_ssl_verify, watch, interval):
    """
    Check ITSI demo readiness against a live instance.

    Verifies that services, health scores, KPI data, entities, and correlation
    searches are all active. Shows active degrade scenario status and remaining
    time. Use --watch for a live-refreshing readiness board.

    Example:
      python -m itsi_accelerator probe \\
        --url https://my-show.splunkcloud.com \\
        --token $SPLUNK_TOKEN \\
        --pack apm_pack.json --watch
    """
    from itsi_accelerator.probe.checker import ProbeChecker
    from rich.live import Live
    from rich.layout import Layout
    from rich.table import Table as RichTable
    from rich.panel import Panel as RichPanel
    from rich.text import Text
    import datetime
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    pack_dict: dict = {}
    if pack:
        try:
            pack_dict = json.loads(Path(pack).read_text())
        except Exception as e:
            console.print(f"[yellow]Warning: could not load pack '{pack}': {e}[/]")

    checker = ProbeChecker(
        url=url,
        token=token,
        pack_dict=pack_dict,
        verify_ssl=not no_ssl_verify,
    )

    # Shared session for activity log queries
    _session = requests.Session()
    _session.verify = not no_ssl_verify
    _session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    _activity_log: list[tuple[str, str, str]] = []  # (timestamp_str, severity_color, message)
    _MAX_LOG_LINES = 20

    def _fetch_activity() -> None:
        """Query itsi_tracked_alerts for recent notables and append new entries to activity log."""
        try:
            resp = _session.post(
                f"{url.rstrip('/')}/services/search/jobs/export",
                data={
                    "search": (
                        "search index=itsi_tracked_alerts earliest=-5m "
                        "| eval ts=strftime(_time,'%H:%M:%S') "
                        "| eval sev=coalesce(severity_label,severity,'info') "
                        "| eval svc=coalesce(itsi_service_name,source,'unknown') "
                        "| eval msg=coalesce(alert_description,title,event_title,'event') "
                        "| table ts, sev, svc, msg "
                        "| sort -_time | head 10"
                    ),
                    "output_mode": "json",
                    "earliest_time": "-5m",
                    "latest_time": "now",
                    "count": 10,
                },
                timeout=10,
            )
            new_entries = []
            for line in resp.text.strip().splitlines():
                try:
                    obj = json.loads(line)
                    r = obj.get("result")
                    if r:
                        ts = r.get("ts", "?")
                        sev = r.get("sev", "info").lower()
                        svc = r.get("svc", "")
                        msg = r.get("msg", "")
                        sev_color = "red" if "critical" in sev else "yellow" if "high" in sev or "warn" in sev else "cyan"
                        label = f"[{sev_color}]{sev.upper()[:4]}[/]"
                        entry = (ts, sev_color, f"{label} [{svc}] {msg}")
                        # Deduplicate by message content (same ts+msg already in log)
                        if not any(e[2] == entry[2] for e in _activity_log):
                            new_entries.append(entry)
                except json.JSONDecodeError:
                    pass
            if new_entries:
                _activity_log.extend(new_entries)
                # Keep only the most recent MAX_LOG_LINES entries
                while len(_activity_log) > _MAX_LOG_LINES:
                    _activity_log.pop(0)
        except Exception:
            pass  # Activity log is best-effort; don't break probe on query failure

    def _build_readiness_panel(report) -> RichPanel:
        """Render the readiness board as a Rich panel."""
        table = RichTable(show_header=False, show_edge=False, box=None, padding=(0, 1))
        table.add_column("icon", width=3)
        table.add_column("check", style="bold", min_width=24)
        table.add_column("message")
        table.add_column("detail", style="dim")

        for check in report.checks:
            icon_txt = Text(check.icon, style=check.color)
            table.add_row(
                icon_txt,
                check.name,
                Text(check.message, style=check.color if check.status in ("fail", "warn") else ""),
                check.detail,
            )

        ts = datetime.datetime.fromtimestamp(report.checked_at).strftime("%H:%M:%S")
        footer = f"Score: {report.score}%  |  Checked: {ts}"
        if watch:
            footer += f"  |  Refreshing every {interval}s  (Ctrl+C to stop)"

        verdict_text = Text(f" {report.verdict} ", style=f"bold white on {report.verdict_color}")
        title = Text.assemble("ITSI Demo Readiness  ", verdict_text)
        if pack:
            title = Text.assemble(f"ITSI Demo Readiness [{Path(pack).name}]  ", verdict_text)

        return RichPanel(table, title=title, subtitle=footer)

    def _build_activity_panel() -> RichPanel:
        """Render the rolling activity log as a Rich panel."""
        lines = Text()
        if not _activity_log:
            lines.append("No ITSI events in last 5 minutes.", style="dim")
        else:
            for ts, _, msg in reversed(_activity_log[-_MAX_LOG_LINES:]):
                lines.append(f"{ts}  ", style="dim")
                lines.append_text(Text.from_markup(msg))
                lines.append("\n")
        return RichPanel(lines, title="[bold cyan]Activity Log[/] [dim](itsi_tracked_alerts, last 5m)[/]")

    def _build_display(report) -> Layout:
        """Build a two-panel layout: readiness board on top, activity log on bottom."""
        layout = Layout()
        layout.split_column(
            Layout(_build_readiness_panel(report), name="readiness", ratio=2),
            Layout(_build_activity_panel(), name="activity", ratio=1),
        )
        return layout

    if not watch:
        with console.status("[cyan]Probing ITSI...[/]"):
            report = checker.run()
        console.print(_build_readiness_panel(report))
        if output:
            Path(output).write_text(json.dumps(report.to_dict(), indent=2))
            console.print(f"Report saved to [cyan]{output}[/]")
        if not report.ready:
            sys.exit(1)
        return

    # ── Watch mode: live-refreshing board with activity log ────────────────────
    report = checker.run()
    _fetch_activity()
    with Live(_build_display(report), console=console, refresh_per_second=4, screen=False) as live:
        try:
            tick = 0
            while True:
                time.sleep(0.1)
                tick += 1
                # Refresh readiness checks every `interval` seconds
                if tick % (interval * 10) == 0:
                    report = checker.run()
                # Refresh activity log every 15s (more frequent than probe checks)
                if tick % 150 == 0:
                    _fetch_activity()
                live.update(_build_display(report))
        except KeyboardInterrupt:
            pass
    console.print("[dim]Watch stopped.[/]")


# ── preflight ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--url", "-u", required=True)
@click.option("--token", "-t", required=True, envvar="SPLUNK_TOKEN")
@click.option("--output", "-o", default=None)
@click.option("--no-ssl-verify", is_flag=True, default=True)
def preflight(url, token, output, no_ssl_verify):
    """Check whether Splunk data is ready for ITSI onboarding."""
    from itsi_accelerator.preflight.checker import PreflightChecker

    console.print(f"[bold cyan]Pre-flight check:[/] {url}")
    checker = PreflightChecker(url, token, verify_ssl=not no_ssl_verify)
    report = checker.run()

    for check in report.checks:
        icon = "[green]✓[/]" if check.passed else "[red]✗[/]"
        console.print(f"  {icon} [bold]{check.name}[/]: {check.message}")

    score_color = "green" if report.score >= 80 else "yellow" if report.score >= 50 else "red"
    console.print(f"\n[bold]Readiness: [{score_color}]{report.score}%[/][/]")

    if output:
        Path(output).write_text(json.dumps(report.to_dict(), indent=2))
        console.print(f"Report saved to [cyan]{output}[/]")


# ── import ────────────────────────────────────────────────────────────────────

@cli.command(name="import")
@click.option("--pack", "-p", required=True)
@click.option("--url", "-u", required=True)
@click.option("--token", "-t", required=True, envvar="SPLUNK_TOKEN")
@click.option("--no-ssl-verify", is_flag=True, default=True)
def import_pack(pack, url, token, no_ssl_verify):
    """Import a generated content pack into live ITSI via REST API."""
    import requests as req
    pack_data = json.loads(Path(pack).read_text())

    import urllib3
    urllib3.disable_warnings()
    session = req.Session()
    session.verify = not no_ssl_verify
    session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    try:
        resp = session.post(
            f"{url.rstrip('/')}/servicesNS/nobody/SA-ITOA/itsi/content_packs/import",
            data=json.dumps({"content_pack": pack_data, "overwrite": False}),
            timeout=60,
        )
        resp.raise_for_status()
        console.print("[bold green]Import successful.[/]")
    except Exception as e:
        console.print(f"[bold red]Import failed:[/] {e}")
        sys.exit(1)


# ── apm ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--source", "-s", default="splunk_o11y", show_default=True,
              type=click.Choice(["splunk_o11y", "appd"], case_sensitive=False),
              help="APM source: splunk_o11y (Splunk Observability Cloud) or appd (AppDynamics, coming soon)")
@click.option("--token", "-t", required=True, envvar="SPLUNK_ACCESS_TOKEN",
              help="API token for the APM source (env: SPLUNK_ACCESS_TOKEN)")
@click.option("--realm", "-r", default="us0", show_default=True,
              help="Splunk O11y realm (us0, us1, eu0, jp0, au0)")
@click.option("--environment", "-e", required=True,
              help="APM environment name (e.g. prod, staging, production)")
@click.option("--lookback", default=60, show_default=True,
              help="Lookback window in minutes when pulling the service map")
@click.option("--context", "-c", default="",
              help="Additional context for Claude (industry, team, compliance, etc.)")
@click.option("--output", "-o", default="apm_pack.json", show_default=True)
@click.option("--index", default="main", show_default=True, help="Splunk index for generated KPI SPL")
@click.option("--ai-kpis/--template-kpis", default=True, show_default=True)
@click.option("--no-ssl-verify", is_flag=True, default=False)
def apm(source, token, realm, environment, lookback, context, output, index, ai_kpis, no_ssl_verify):
    """
    Generate ITSI service tree from a live APM service map.

    Pulls the real service topology from your APM tool, classifies each service
    with ITSI CI types and monitoring tiers via Claude, then generates KPIs.

    Example (Splunk O11y):
      python -m itsi_accelerator apm \\
        --token $SPLUNK_ACCESS_TOKEN --realm us1 --environment prod \\
        -o prod_pack.json
    """
    if source == "appd":
        console.print("[red]AppDynamics source is not yet implemented.[/]")
        console.print("[dim]Set --source splunk_o11y to use Splunk Observability Cloud.[/]")
        sys.exit(1)

    from itsi_accelerator.apm.splunk_o11y import SplunkO11yClient
    from itsi_accelerator.ai.service_discoverer import classify_apm_services

    console.print(Panel(
        f"[bold]APM source:[/] Splunk O11y ({realm})\n"
        f"[bold]Environment:[/] {environment}\n"
        f"[bold]Lookback:[/] {lookback} minutes",
        title="[cyan]APM Service Map Import[/]",
    ))

    client = SplunkO11yClient(realm=realm, token=token, verify_ssl=not no_ssl_verify)

    with console.status("[cyan]Pulling service map from Splunk O11y APM...[/]"):
        try:
            service_map = client.get_service_map(environment=environment, lookback_minutes=lookback)
        except Exception as e:
            console.print(f"[bold red]Failed to fetch service map:[/] {e}")
            sys.exit(1)

    nodes = service_map["nodes"]
    edges = service_map["edges"]
    console.print(f"[dim]Found {len(nodes)} services, {len(edges)} dependency edges[/]")

    with console.status("[cyan]Claude is classifying the APM topology into ITSI services...[/]"):
        discovery = classify_apm_services(nodes=nodes, edges=edges, context=context)

    pack = _build_pack_from_discovery(
        discovery=discovery,
        title=f"APM Import: {environment} ({realm})",
        index=index,
        ai_kpis=ai_kpis,
        context=context,
    )

    Path(output).write_text(json.dumps(pack.to_dict(), indent=2))
    console.print(f"\n[bold green]Done.[/] {len(pack.services)} services -> [cyan]{output}[/]")
    _print_service_table(pack)

    gaps = discovery.get("coverage_gaps", [])
    if gaps:
        console.print("\n[yellow]Coverage gaps to address:[/]")
        for g in gaps:
            console.print(f"  • {g}")


# ── diagram ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--image", "-i", required=True,
              help="Architecture diagram file (PNG, JPEG, GIF, WEBP, or SVG)")
@click.option("--context", "-c", default="",
              help="Additional context (industry, stack, SLA requirements)")
@click.option("--output", "-o", default="diagram_pack.json", show_default=True)
@click.option("--index", default="main", show_default=True, help="Splunk index for generated KPI SPL")
@click.option("--ai-kpis/--template-kpis", default=True, show_default=True)
def diagram(image, context, output, index, ai_kpis):
    """
    AI-driven: analyze an architecture diagram image and generate an ITSI content pack.

    Claude reads the diagram visually (or as SVG text) and infers the full service
    tree — services, dependencies, CI types, and monitoring tiers.

    Supported formats: PNG, JPEG, GIF, WEBP, SVG

    Example:
      python -m itsi_accelerator diagram \\
        -i architecture.png -c "healthcare SaaS, 99.9% SLA" \\
        -o arch_pack.json
    """
    from itsi_accelerator.ai.diagram_analyzer import analyze_diagram

    console.print(Panel(
        f"[bold]Diagram:[/] {image}\n"
        + (f"[bold]Context:[/] {context}" if context else "[dim]No additional context provided[/]"),
        title="[cyan]Diagram Analysis[/]",
    ))

    with console.status("[cyan]Claude is analyzing the diagram...[/]"):
        try:
            discovery = analyze_diagram(image_path=image, context=context)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[bold red]Error:[/] {e}")
            sys.exit(1)

    summary = discovery.get("architecture_summary", "")
    if summary:
        console.print(f"\n[bold]Architecture:[/] {summary}")

    pack = _build_pack_from_discovery(
        discovery=discovery,
        title=f"Diagram Import: {Path(image).stem}",
        index=index,
        ai_kpis=ai_kpis,
        context=context,
    )

    Path(output).write_text(json.dumps(pack.to_dict(), indent=2))
    console.print(f"\n[bold green]Done.[/] {len(pack.services)} services -> [cyan]{output}[/]")
    _print_service_table(pack)

    gaps = discovery.get("coverage_gaps", [])
    if gaps:
        console.print("\n[yellow]Coverage gaps to address:[/]")
        for g in gaps:
            console.print(f"  • {g}")


# ── degrade ───────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--pack", "-p", default=None, help="Content pack JSON — used to know what services exist. Optional when --vertical is specified.")
@click.option("--scenario", "-s", default=None,
              help="Scenario name to run (substring match). Omit to list all and choose interactively.")
@click.option("--target", default="simulate", show_default=True,
              type=click.Choice(["simulate", "k8s", "hec", "otel-demo"], case_sensitive=False),
              help="Execution target. 'simulate' is a safe dry-run.")
@click.option("--duration", "-d", default=300, show_default=True,
              help="Seconds to hold the degradation before auto-recovering")
@click.option("--namespace", "-n", default="default", show_default=True, help="Kubernetes namespace")
@click.option("--kubeconfig", default="~/.kube/config", show_default=True)
@click.option("--hec-url", default="", help="Splunk HEC URL (required for --target hec)")
@click.option("--hec-token", default="", envvar="SPLUNK_HEC_TOKEN",
              help="Splunk HEC token (env: SPLUNK_HEC_TOKEN)")
@click.option("--featureflag-url", default="http://localhost:8013", show_default=True,
              help="OTel Demo feature flag service URL (used with --target otel-demo)")
@click.option("--vertical", default=None,
              help="Use pre-built scenarios for a known vertical (e.g. otel-demo). Skips Claude.")
@click.option("--context", "-c", default="",
              help="Additional context for Claude scenario generation (app name, stack, industry)")
@click.option("--all", "run_all", is_flag=True, default=False,
              help="Run all generated scenarios sequentially")
@click.option("--index", default="main", show_default=True, help="Splunk index (used in HEC events)")
def degrade(pack, scenario, target, duration, namespace, kubeconfig, hec_url, hec_token,
            featureflag_url, vertical, context, run_all, index):
    """
    Inject a degradation scenario and auto-recover after --duration seconds.

    By default Claude generates realistic failure scenarios from your content pack.
    Use --vertical otel-demo to skip the AI call and use hardcoded astroshop scenarios.

    Safe by default: --target simulate (dry-run) prints what WOULD happen without
    touching anything.

    Targets:
      simulate   — dry-run, prints commands and talking points (default)
      k8s        — executes kubectl commands against your cluster
      otel-demo  — toggles OpenTelemetry Demo feature flags (cleanest for astroshop)
      hec        — sends synthetic events to Splunk HEC

    Examples:
      # OTel Demo — hardcoded scenarios, no AI call
      python -m itsi_accelerator degrade --pack astroshop_pack.json \\
        --vertical otel-demo --target otel-demo

      # Run the payment failure scenario immediately
      python -m itsi_accelerator degrade --pack astroshop_pack.json \\
        --vertical otel-demo --scenario payment --target otel-demo --duration 120

      # AI-generated scenarios against k8s
      python -m itsi_accelerator degrade --pack apm_pack.json \\
        --scenario cascade --target k8s --namespace otel-demo --duration 300
    """
    from itsi_accelerator.degrade.executor import run_scenario
    from itsi_accelerator.templates.scenarios import get_scenarios_for_vertical, list_scenario_verticals

    # --pack is optional when --vertical is specified (pre-built scenarios don't need a pack)
    pack_dict: dict = {}
    services_raw: list = []
    if pack:
        pack_dict = json.loads(Path(pack).read_text())
        services_raw = pack_dict.get("data", {}).get("services", [])
    elif not vertical:
        console.print("[red]--pack is required unless --vertical is specified.[/]")
        sys.exit(1)

    console.print(Panel(
        (f"[bold]Pack:[/] {pack_dict.get('title', pack)}\n" if pack else "")
        + f"[bold]Target:[/] {target}\n"
        + f"[bold]Duration:[/] {duration}s"
        + (f"\n[bold]Vertical:[/] {vertical} [dim](pre-built scenarios)[/]" if vertical else ""),
        title="[cyan]ITSI Degradation Scenarios[/]",
    ))

    # Use pre-built scenarios if a known vertical is specified — no AI call needed
    if vertical:
        scenarios = get_scenarios_for_vertical(vertical)
        if scenarios is None:
            available = ", ".join(list_scenario_verticals())
            console.print(f"[red]No pre-built scenarios for vertical '{vertical}'.[/] Available: {available}")
            console.print("[dim]Falling back to Claude-generated scenarios...[/]")
            scenarios = None
        else:
            console.print(f"[green]Loaded {len(scenarios)} pre-built scenarios for '{vertical}'.[/]")
    else:
        scenarios = None

    if scenarios is None:
        # Build service summary for Claude
        from itsi_accelerator.ai.scenario_generator import generate_scenarios
        services_summary = []
        for s in services_raw:
            kpis = [k for k in s.get("kpis", []) if k.get("title") != "ServiceHealthScore"]
            services_summary.append({
                "name": s["title"],
                "description": s.get("description", ""),
                "ci_type": _infer_ci_type_from_tags(s.get("tags", [])),
                "sla_critical": "sla-critical" in " ".join(s.get("tags", [])).lower(),
                "kpis": kpis[:4],
            })
        with console.status("[cyan]Claude is generating demo scenarios...[/]"):
            scenarios = generate_scenarios(services=services_summary, context=context)

    if not scenarios:
        console.print("[red]No scenarios generated.[/]")
        sys.exit(1)

    # Print scenario menu
    source_label = "pre-built" if vertical and get_scenarios_for_vertical(vertical) else "generated"
    console.print(f"\n[bold]{len(scenarios)} {source_label} scenarios:[/]\n")
    table = Table(show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Scenario", style="bold")
    table.add_column("Service")
    table.add_column("Type", style="cyan")
    table.add_column("Severity", style="yellow")
    table.add_column("Alert in")
    for i, sc in enumerate(scenarios, 1):
        sev = sc.get("severity", "medium")
        sev_color = "red" if sev == "critical" else "yellow" if sev == "high" else "white"
        table.add_row(
            str(i),
            sc["name"],
            sc.get("service_name", ""),
            sc.get("failure_type", ""),
            f"[{sev_color}]{sev}[/]",
            f"~{sc.get('time_to_alert_seconds', '?')}s",
        )
    console.print(table)

    # Select scenario(s) to run
    to_run: list[dict] = []
    if run_all:
        to_run = scenarios
    elif scenario:
        # Substring match on name
        matches = [sc for sc in scenarios if scenario.lower() in sc["name"].lower()
                   or scenario.lower() in sc["failure_type"].lower()
                   or scenario.lower() in sc["service_name"].lower()]
        if not matches:
            console.print(f"[red]No scenario matching '{scenario}'.[/] Available: "
                          + ", ".join(sc["name"] for sc in scenarios))
            sys.exit(1)
        to_run = matches[:1]
    else:
        # Interactive selection
        console.print("\nEnter scenario number to run (or 'q' to quit, 'a' to run all): ", end="")
        choice = click.prompt("", default="q")
        if choice.lower() == "q":
            sys.exit(0)
        if choice.lower() == "a":
            to_run = scenarios
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(scenarios):
                    to_run = [scenarios[idx]]
                else:
                    console.print("[red]Invalid selection.[/]")
                    sys.exit(1)
            except ValueError:
                console.print("[red]Invalid input.[/]")
                sys.exit(1)

    if target == "simulate":
        console.print("\n[yellow]Running in SIMULATE mode — no changes will be made.[/]")
    elif target == "k8s":
        console.print(f"\n[yellow]Running against k8s namespace '{namespace}'.[/]")
        if not click.confirm("Proceed?"):
            sys.exit(0)

    # Run each selected scenario
    def _print(msg: str):
        console.print(msg)

    all_ok = True
    for sc in to_run:
        ok = run_scenario(
            scenario=sc,
            target=target,
            duration=duration,
            namespace=namespace,
            kubeconfig=kubeconfig,
            hec_url=hec_url,
            hec_token=hec_token,
            featureflag_url=featureflag_url,
            print_fn=_print,
        )
        all_ok = all_ok and ok

    if not all_ok:
        sys.exit(1)


# ── neap ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--pack", "-p", required=True, help="Content pack JSON (output of discover/apm/diagram/cmdb)")
@click.option("--output", "-o", default=None,
              help="Output path for NEAP bundle JSON (default: <pack>_neap_bundle.json)")
@click.option("--index", default="main", show_default=True, help="Splunk index for correlation search SPL")
@click.option("--context", "-c", default="", help="Additional context for Claude (industry, stack, etc.)")
@click.option("--silence", default=15, show_default=True,
              help="Episode break-after-silence window in minutes")
@click.option("--no-correlation-searches", is_flag=True, default=False,
              help="Skip AI-generated correlation searches (NEAPs only)")
@click.option("--validate", is_flag=True, default=False,
              help="Dry-run each correlation search SPL against a live Splunk instance and flag zero-result searches")
@click.option("--validate-url", default="", envvar="SPLUNK_URL",
              help="Splunk base URL for validation (env: SPLUNK_URL), e.g. https://my-show.splunkcloud.com")
@click.option("--validate-token", default="", envvar="SPLUNK_TOKEN",
              help="Splunk Bearer token for validation (env: SPLUNK_TOKEN)")
def neap(pack, output, index, context, silence, no_correlation_searches,
         validate, validate_url, validate_token):
    """
    Generate NEAPs + correlation searches for an existing content pack.

    NEAPs (Notable Event Aggregation Policies) are generated from templates — one per
    service, grouping notables into episodes. Correlation searches are AI-generated
    SPL that fire notables into those episodes.

    Use --validate to dry-run each SPL against a live Splunk instance. Zero-result
    searches are flagged as warnings — the SPL is likely referencing wrong index/fields.

    Output is a separate JSON bundle loaded via the ITSI REST API or packaged into
    a Splunk app alongside the content pack.

    Examples:
      python -m itsi_accelerator neap --pack apm_pack.json -o apm_neap_bundle.json

      python -m itsi_accelerator neap --pack apm_pack.json \\
        --validate --validate-url https://my-show.splunkcloud.com --validate-token <token>
    """
    from itsi_accelerator.core.models import CorrelationSearch, NotableEventAggregationPolicy
    from itsi_accelerator.templates.neap_templates import build_neaps

    pack_path = Path(pack)
    pack_dict = json.loads(pack_path.read_text())
    pack_title = pack_dict.get("title", pack_path.stem)

    services_raw = pack_dict.get("data", {}).get("services", [])
    if not services_raw:
        console.print("[red]No services found in pack.[/]")
        sys.exit(1)

    console.print(Panel(
        f"[bold]Pack:[/] {pack_title}\n"
        f"[bold]Services:[/] {len(services_raw)}\n"
        f"[bold]Silence window:[/] {silence} minutes",
        title="[cyan]NEAP + Correlation Search Generator[/]",
    ))

    # Rebuild lightweight Service stubs (just _key + title + depends_on) for NEAP builder
    from itsi_accelerator.core.models import Service, EntityRule
    svc_stubs = []
    for s in services_raw:
        stub = Service(
            title=s["title"],
            description=s.get("description", ""),
        )
        stub._key = s["_key"]
        stub.services_depends_on = s.get("services_depends_on", [])
        svc_stubs.append(stub)

    # 1. Generate NEAPs (template-based, no AI)
    neap_objects = build_neaps(svc_stubs, break_after_silence_minutes=silence)
    console.print(f"[dim]Generated {len(neap_objects)} NEAPs[/]")

    # 2. Generate correlation searches (AI, one batched call)
    cs_objects: list[CorrelationSearch] = []
    if not no_correlation_searches:
        from itsi_accelerator.ai.correlation_search_generator import generate_correlation_searches

        # Build service summary for Claude — include KPI names for context
        services_summary = []
        key_to_name = {s["_key"]: s["title"] for s in services_raw}
        for s in services_raw:
            kpis = s.get("kpis", [])
            # filter out the synthetic ServiceHealthScore KPI
            real_kpis = [k for k in kpis if k.get("title") != "ServiceHealthScore"]
            services_summary.append({
                "name": s["title"],
                "description": s.get("description", ""),
                "ci_type": _infer_ci_type_from_tags(s.get("tags", [])),
                "sla_critical": "sla-critical" in " ".join(s.get("tags", [])).lower(),
                "kpis": real_kpis[:4],
            })

        with console.status("[cyan]Claude is generating correlation searches...[/]"):
            cs_dicts = generate_correlation_searches(
                services=services_summary,
                index=index,
                context=context,
            )

        # Map service names back to keys
        name_to_key = {s["title"]: s["_key"] for s in services_raw}
        for cs_dict in cs_dicts:
            svc_key = name_to_key.get(cs_dict.get("service_name", ""), "")
            cs_objects.append(CorrelationSearch(
                name=cs_dict["name"],
                description=cs_dict.get("description", ""),
                search=cs_dict["search"],
                service_key=svc_key,
                severity=cs_dict.get("severity", "medium"),
                alert_title=cs_dict.get("alert_title", cs_dict["name"]),
                cron_schedule=cs_dict.get("cron_schedule", "*/5 * * * *"),
            ))
        console.print(f"[dim]Generated {len(cs_objects)} correlation searches[/]")

    # 3. Optionally validate SPL against a live Splunk instance
    if validate and cs_objects:
        if not validate_url or not validate_token:
            console.print("[yellow]--validate requires --validate-url and --validate-token (or SPLUNK_URL/SPLUNK_TOKEN env vars). Skipping validation.[/]")
        else:
            import requests
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            session = requests.Session()
            session.verify = False
            session.headers.update({
                "Authorization": f"Bearer {validate_token}",
            })

            console.print(f"\n[bold]Validating {len(cs_objects)} correlation search(es) against {validate_url}...[/]")
            val_table = Table(show_lines=False)
            val_table.add_column("Search", style="bold", max_width=40)
            val_table.add_column("Result count", justify="right")
            val_table.add_column("Status")

            warn_count = 0
            for cs in cs_objects:
                # Run search with count=1 — we only care whether ANY results exist
                spl = cs.search if cs.search.startswith("search ") else f"search {cs.search}"
                try:
                    resp = session.post(
                        f"{validate_url.rstrip('/')}/services/search/jobs/export",
                        data={
                            "search": spl,
                            "output_mode": "json",
                            "earliest_time": "-60m",
                            "latest_time": "now",
                            "count": 10,
                        },
                        timeout=20,
                    )
                    result_count = sum(
                        1 for line in resp.text.strip().splitlines()
                        if '"result"' in line
                    )
                    if result_count == 0:
                        status = "[yellow]WARN: 0 results[/]"
                        warn_count += 1
                    else:
                        status = f"[green]OK[/]"
                    val_table.add_row(cs.name[:40], str(result_count), status)
                except Exception as e:
                    val_table.add_row(cs.name[:40], "—", f"[red]ERROR: {str(e)[:60]}[/]")
                    warn_count += 1

            console.print(val_table)
            if warn_count:
                console.print(
                    f"\n[yellow]{warn_count} search(es) returned no results.[/] "
                    "These may reference wrong index names or field values. "
                    "Edit the SPL in the bundle JSON before loading into ITSI."
                )
            else:
                console.print(f"\n[green]All {len(cs_objects)} searches returned results.[/]")

    # 4. Serialize
    bundle = {
        "title": pack_title,
        "_pack_key": pack_dict.get("_key", ""),
        "correlation_searches": [cs.to_dict() for cs in cs_objects],
        "notable_event_aggregation_policies": [n.to_dict() for n in neap_objects],
    }

    out_path = Path(output) if output else pack_path.with_name(pack_path.stem + "_neap_bundle.json")
    out_path.write_text(json.dumps(bundle, indent=2))

    console.print(f"\n[bold green]Done.[/]")
    console.print(f"  NEAPs:               [cyan]{len(neap_objects)}[/]")
    console.print(f"  Correlation searches: [cyan]{len(cs_objects)}[/]")
    console.print(f"  Output:              [cyan]{out_path}[/]")
    console.print(
        "\n[dim]Load via ITSI REST API:\n"
        "  NEAPs:   POST /itsi/notable_event_aggregation_policy\n"
        "  Corr:    POST /saved/searches (with itsi_event_generator action)\n"
        "Or package into a Splunk app alongside your content pack.[/]"
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_pack_from_discovery(
    discovery: dict,
    title: str,
    index: str,
    ai_kpis: bool,
    context: str,
) -> "ContentPack":
    """
    Shared builder: turns a Claude discovery dict (services, architecture_summary,
    recommended_index, coverage_gaps) into a fully populated ContentPack.
    Automatically generates entities for each service.
    Used by: discover, apm, diagram.
    """
    from itsi_accelerator.ai.kpi_generator import generate_kpis
    from itsi_accelerator.core.models import ContentPack, Service, KPI, EntityRule, Entity

    services_data = discovery.get("services", [])
    summary = discovery.get("architecture_summary", "")
    rec_index = discovery.get("recommended_index", index)

    console.print(f"[dim]Discovered {len(services_data)} services[/]")

    pack = ContentPack(title=title, description=summary)
    name_to_key: dict[str, str] = {}

    for svc_data in services_data:
        svc = Service(
            title=svc_data["name"],
            description=svc_data.get("description", ""),
            tags=["field-accelerator", "ai-discovered", svc_data.get("monitoring_tier", "")],
        )
        entity_field = svc_data.get("entity_field", "host")
        svc.entity_rules.append(EntityRule(field=entity_field, value="*", rule_type="matches"))
        name_to_key[svc_data["name"]] = svc._key

        ci_type = svc_data.get("ci_type", "app_server")
        sla_critical = svc_data.get("sla_critical", False)

        if ci_type != "business_service":
            if ai_kpis:
                with console.status(f"[cyan]Generating KPIs for {svc_data['name']}...[/]"):
                    try:
                        kpi_result = generate_kpis(
                            service_name=svc_data["name"],
                            service_description=svc_data.get("description", ""),
                            ci_type=ci_type,
                            index=rec_index,
                            sla_critical=sla_critical,
                            industry_context=context,
                        )
                        for kpi_def in kpi_result.get("kpis", []):
                            spl = kpi_def.get("base_search", "").replace("{index}", rec_index)
                            svc.add_kpi(KPI(
                                title=kpi_def["title"],
                                base_search=spl,
                                unit=kpi_def.get("unit", ""),
                                aggregate_statop=kpi_def.get("aggregate_statop", "avg"),
                                description=kpi_def.get("description", ""),
                            ))
                    except Exception as e:
                        console.print(f"[yellow]KPI generation failed for {svc_data['name']}: {e}. Using templates.[/]")
                        _apply_template_kpis(svc, ci_type, rec_index)
            else:
                _apply_template_kpis(svc, ci_type, rec_index)

        pack.add_service(svc)

        # Auto-generate an entity for each service so it's immediately usable in ITSI
        entity = Entity(
            title=svc_data["name"],
            identifier_fields=[entity_field],
            informational_fields=[
                {"alias": "Service Type", "field": "ci_type"},
                {"alias": "Environment", "field": "environment"},
            ],
            service_key=svc._key,
        )
        pack.entities.append(entity)

    # Wire dependencies
    for svc_data in services_data:
        parent_name = svc_data.get("parent", "")
        if not parent_name:
            continue
        parent_key = name_to_key.get(parent_name)
        child_key = name_to_key.get(svc_data["name"])
        if parent_key and child_key:
            parent_svc = next((s for s in pack.services if s._key == parent_key), None)
            if parent_svc and child_key not in parent_svc.services_depends_on:
                parent_svc.services_depends_on.append(child_key)

    return pack


def _apply_template_kpis(svc, ci_type: str, index: str) -> None:
    from itsi_accelerator.templates.kpi_library import get_kpis_for_service_type, render_kpi
    from itsi_accelerator.core.models import KPI
    for tmpl in get_kpis_for_service_type(ci_type):
        rendered = render_kpi(tmpl, index=index)
        svc.add_kpi(KPI(
            title=rendered["title"],
            base_search=rendered["base_search"],
            unit=rendered.get("unit", ""),
            aggregate_statop=rendered.get("aggregate_statop", "avg"),
            description=rendered.get("description", ""),
        ))


def _infer_ci_type_from_tags(tags: list[str]) -> str:
    """Best-effort CI type inference from service tags (used by neap command for existing packs)."""
    tag_str = " ".join(tags).lower()
    for ci_type in [
        "database", "web_server", "app_server", "kubernetes", "cache",
        "message_queue", "api_gateway", "auth_service", "load_balancer",
        "streaming", "business_service",
    ]:
        if ci_type.replace("_", " ") in tag_str or ci_type in tag_str:
            return ci_type
    return "app_server"


def _print_service_table(pack) -> None:
    table = Table(show_lines=False)
    table.add_column("Service", style="bold")
    table.add_column("KPIs", justify="right", style="cyan")
    table.add_column("Tags")
    for svc in pack.services:
        table.add_row(svc.title, str(len(svc.kpis)), ", ".join(svc.tags[:3]))
    console.print(table)
