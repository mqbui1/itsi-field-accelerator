"""CLI entry point for the ITSI Field Accelerator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()


@click.group()
@click.version_option("0.2.0")
def cli():
    """ITSI Field Accelerator — fast-track ITSI onboarding from CMDB data, vertical templates, or plain-English descriptions."""
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


# ── bootstrap ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--vertical", "-v", required=True, help="Vertical: banking, healthcare, retail, telecom, manufacturing, generic")
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
    from itsi_accelerator.ai.kpi_generator import generate_kpis
    from itsi_accelerator.cmdb.parser import CMDBParser
    from itsi_accelerator.templates.kpi_library import get_kpis_for_service_type, render_kpi
    from itsi_accelerator.core.models import ContentPack, Service, KPI, EntityRule, new_id

    console.print(Panel(
        f"[bold]Discovering service tree...[/]\n[dim]{description[:120]}{'...' if len(description) > 120 else ''}[/]",
        title="[cyan]Claude AI Discovery[/]",
    ))

    # Step 1: Claude discovers the service tree
    with console.status("[cyan]Analyzing architecture...[/]"):
        discovery = discover_services(description, context=context)

    services_data = discovery.get("services", [])
    summary = discovery.get("architecture_summary", "")
    gaps = discovery.get("coverage_gaps", [])
    rec_index = discovery.get("recommended_index", index)

    console.print(f"\n[bold]Architecture:[/] {summary}")
    console.print(f"[dim]Discovered {len(services_data)} services[/]")

    # Step 2: Build the content pack
    pack = ContentPack(
        title=f"AI Discovery: {description[:50]}...",
        description=summary,
    )

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

        if ci_type == "business_service":
            # Top-level services get no KPIs — health rolls up from children
            pass
        elif ai_kpis:
            # Claude generates custom KPIs per service
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
                        kpi = KPI(
                            title=kpi_def["title"],
                            base_search=spl,
                            unit=kpi_def.get("unit", ""),
                            aggregate_statop=kpi_def.get("aggregate_statop", "avg"),
                            description=kpi_def.get("description", ""),
                        )
                        svc.add_kpi(kpi)
                except Exception as e:
                    console.print(f"[yellow]KPI generation failed for {svc_data['name']}: {e}. Using templates.[/]")
                    _apply_template_kpis(svc, ci_type, rec_index)
        else:
            _apply_template_kpis(svc, ci_type, rec_index)

        pack.add_service(svc)

    # Step 3: Wire dependencies
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

    # Step 4: Save
    pack_dict = pack.to_dict()
    Path(output).write_text(json.dumps(pack_dict, indent=2))

    console.print(f"\n[bold green]Done.[/] {len(pack.services)} services -> [cyan]{output}[/]")
    _print_service_table(pack)

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


# ── helpers ───────────────────────────────────────────────────────────────────

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


def _print_service_table(pack) -> None:
    table = Table(show_lines=False)
    table.add_column("Service", style="bold")
    table.add_column("KPIs", justify="right", style="cyan")
    table.add_column("Tags")
    for svc in pack.services:
        table.add_row(svc.title, str(len(svc.kpis)), ", ".join(svc.tags[:3]))
    console.print(table)
