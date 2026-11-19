"""CLI entry point for the ITSI Field Accelerator."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()


@click.group()
@click.version_option("0.1.0")
def cli():
    """ITSI Field Accelerator — fast-track ITSI onboarding from CMDB data or vertical templates."""
    pass


# ── cmdb ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--input", "-i", required=True, help="CMDB export file (CSV or JSON)")
@click.option("--output", "-o", default="itsi_content_pack.json", show_default=True, help="Output content pack JSON")
@click.option("--title", "-t", default="CMDB Import", show_default=True, help="Content pack title")
@click.option("--index", default="main", show_default=True, help="Splunk index name for KPI searches")
def cmdb(input, output, title, index):
    """Generate ITSI service tree from a ServiceNow CMDB export (CSV or JSON)."""
    from itsi_accelerator.cmdb.parser import build_pack_from_cmdb

    console.print(f"[bold cyan]Parsing CMDB export:[/] {input}")
    try:
        pack = build_pack_from_cmdb(input, pack_title=title, index=index)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        sys.exit(1)

    out_path = Path(output)
    out_path.write_text(json.dumps(pack.to_dict(), indent=2))

    console.print(f"[bold green]Done.[/] Generated {len(pack.services)} services -> {output}")
    _print_service_tree(pack)


# ── bootstrap ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--vertical", "-v", required=True, help="Vertical name (banking, healthcare, retail, telecom, manufacturing, generic)")
@click.option("--output", "-o", default="demo_content_pack.json", show_default=True, help="Output content pack JSON")
@click.option("--index", default="main", show_default=True, help="Splunk index for KPI searches")
def bootstrap(vertical, output, index):
    """Generate a demo-ready ITSI content pack for a given vertical."""
    from itsi_accelerator.templates.verticals import get_vertical, list_verticals
    from itsi_accelerator.cmdb.parser import CMDBParser

    try:
        rows = get_vertical(vertical)
    except ValueError as e:
        console.print(f"[bold red]Error:[/] {e}")
        console.print(f"Available verticals: {', '.join(list_verticals())}")
        sys.exit(1)

    parser = CMDBParser(index=index)
    pack = parser.build_content_pack(rows, pack_title=f"{vertical.title()} Demo Pack")

    out_path = Path(output)
    out_path.write_text(json.dumps(pack.to_dict(), indent=2))

    console.print(f"[bold green]Done.[/] Bootstrap pack for '{vertical}': {len(pack.services)} services -> {output}")
    _print_service_tree(pack)


# ── kpi-discover ──────────────────────────────────────────────────────────────

@cli.command(name="kpi-discover")
@click.option("--service-type", "-s", required=True, help="Service/CI type (e.g. web_server, database, payment_processor)")
@click.option("--index", default="main", show_default=True, help="Splunk index for SPL")
@click.option("--output", "-o", default=None, help="Optional output JSON file")
def kpi_discover(service_type, index, output):
    """Show recommended KPI templates for a service type or CI class."""
    from itsi_accelerator.templates.kpi_library import (
        get_kpis_for_service_type, render_kpi, CI_CLASS_ALIASES, KPI_TEMPLATES
    )

    kpis = get_kpis_for_service_type(service_type)
    if not kpis:
        console.print(f"[yellow]No templates found for '{service_type}'.[/]")
        console.print(f"Available types: {', '.join(KPI_TEMPLATES.keys())}")
        sys.exit(1)

    rendered = [render_kpi(k, index=index) for k in kpis]

    table = Table(title=f"KPI Templates: {service_type}", show_lines=True)
    table.add_column("KPI Title", style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Unit")
    table.add_column("Yellow Threshold", style="yellow")
    table.add_column("Red Threshold", style="red")
    for k in rendered:
        table.add_row(
            k["title"],
            k.get("metric", ""),
            k.get("unit", ""),
            str(k.get("thresholds", {}).get("yellow") or "adaptive"),
            str(k.get("thresholds", {}).get("red") or "adaptive"),
        )
    console.print(table)

    if output:
        Path(output).write_text(json.dumps(rendered, indent=2))
        console.print(f"Saved to [cyan]{output}[/]")


# ── preflight ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--url", "-u", required=True, help="Splunk REST URL (e.g. https://splunk:8089)")
@click.option("--token", "-t", required=True, envvar="SPLUNK_TOKEN", help="Splunk auth token")
@click.option("--output", "-o", default=None, help="Optional output JSON file")
@click.option("--no-ssl-verify", is_flag=True, default=True, help="Disable SSL verification")
def preflight(url, token, output, no_ssl_verify):
    """Check whether Splunk data is ready for ITSI onboarding."""
    from itsi_accelerator.preflight.checker import PreflightChecker

    console.print(f"[bold cyan]Running pre-flight checks against:[/] {url}")
    checker = PreflightChecker(url, token, verify_ssl=not no_ssl_verify)
    report = checker.run()

    console.print()
    for check in report.checks:
        icon = "[green]✓[/]" if check.passed else "[red]✗[/]"
        console.print(f"  {icon} [bold]{check.name}[/]: {check.message}")

    console.print()
    score_color = "green" if report.score >= 80 else "yellow" if report.score >= 50 else "red"
    console.print(f"[bold]Overall readiness score: [{score_color}]{report.score}%[/][/]")

    if report.score < 80:
        console.print("[yellow]Recommendation:[/] Address failing checks before ITSI onboarding. "
                      "Run with --output to save full report.")

    if output:
        Path(output).write_text(json.dumps(report.to_dict(), indent=2))
        console.print(f"Full report saved to [cyan]{output}[/]")


# ── import ────────────────────────────────────────────────────────────────────

@cli.command(name="import")
@click.option("--pack", "-p", required=True, help="Content pack JSON file to import")
@click.option("--url", "-u", required=True, help="ITSI/Splunk REST URL")
@click.option("--token", "-t", required=True, envvar="SPLUNK_TOKEN", help="Splunk auth token")
@click.option("--no-ssl-verify", is_flag=True, default=True)
def import_pack(pack, url, token, no_ssl_verify):
    """Import a generated content pack into live ITSI via REST API."""
    from itsi_accelerator.core.importer import ITSIImporter
    from itsi_accelerator.core.models import ContentPack

    pack_data = json.loads(Path(pack).read_text())

    # Reconstruct a minimal ContentPack for import
    cp = ContentPack(
        title=pack_data.get("title", "Imported Pack"),
        description=pack_data.get("description", ""),
        _key=pack_data.get("_key", ""),
    )
    # Pass the raw dict to importer
    importer = ITSIImporter(url, token, verify_ssl=not no_ssl_verify)

    if not importer.test_connection():
        console.print("[red]Cannot connect to ITSI. Check URL and token.[/]")
        sys.exit(1)

    console.print(f"[bold cyan]Importing[/] '{cp.title}' into {url} ...")
    # For import, we pass the raw pack dict directly
    try:
        import requests
        resp = importer.session.post(
            f"{url.rstrip('/')}/servicesNS/nobody/SA-ITOA/itsi/content_packs/import",
            data=json.dumps({"content_pack": pack_data, "overwrite": False}),
            timeout=60,
        )
        resp.raise_for_status()
        console.print(f"[bold green]Import successful.[/]")
    except Exception as e:
        console.print(f"[bold red]Import failed:[/] {e}")
        sys.exit(1)


# ── helpers ───────────────────────────────────────────────────────────────────

def _print_service_tree(pack):
    table = Table(title="Generated Services", show_lines=False)
    table.add_column("Service", style="bold")
    table.add_column("KPIs", justify="right", style="cyan")
    table.add_column("Tags")
    for svc in pack.services:
        table.add_row(svc.title, str(len(svc.kpis)), ", ".join(svc.tags[:3]))
    console.print(table)
