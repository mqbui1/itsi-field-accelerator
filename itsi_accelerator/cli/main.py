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
@click.version_option("0.3.0")
def cli():
    """ITSI Field Accelerator — fast-track ITSI onboarding from CMDB data, vertical templates, APM topology, or plain-English descriptions."""
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
@click.option("--pack", "-p", required=True, help="Content pack JSON — used to know what services exist")
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
@click.option("--context", "-c", default="",
              help="Additional context for Claude scenario generation (app name, stack, industry)")
@click.option("--all", "run_all", is_flag=True, default=False,
              help="Run all generated scenarios sequentially")
@click.option("--index", default="main", show_default=True, help="Splunk index (used in HEC events)")
def degrade(pack, scenario, target, duration, namespace, kubeconfig, hec_url, hec_token,
            featureflag_url, context, run_all, index):
    """
    Inject a degradation scenario and auto-recover after --duration seconds.

    Claude generates realistic failure scenarios from your content pack (which services
    exist, what KPIs they have). You pick one to run. The command injects the failure,
    holds it, then recovers — giving the demo audience enough time to see ITSI react.

    Safe by default: --target simulate (dry-run) prints what WOULD happen without
    touching anything.

    Targets:
      simulate   — dry-run, prints commands and talking points (default)
      k8s        — executes kubectl commands against your cluster
      otel-demo  — toggles OpenTelemetry Demo feature flags (cleanest for astroshop)
      hec        — sends synthetic events to Splunk HEC

    Examples:
      # Plan scenarios (no execution)
      python -m itsi_accelerator degrade --pack apm_pack.json

      # Run the cascade scenario against k8s
      python -m itsi_accelerator degrade --pack apm_pack.json \\
        --scenario cascade --target k8s --namespace otel-demo --duration 300

      # OTel Demo feature flag injection
      python -m itsi_accelerator degrade --pack apm_pack.json \\
        --target otel-demo --featureflag-url http://localhost:8013
    """
    from itsi_accelerator.ai.scenario_generator import generate_scenarios
    from itsi_accelerator.degrade.executor import run_scenario

    pack_dict = json.loads(Path(pack).read_text())
    services_raw = pack_dict.get("data", {}).get("services", [])
    if not services_raw:
        console.print("[red]No services found in pack.[/]")
        sys.exit(1)

    # Build service summary for scenario generator
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

    console.print(Panel(
        f"[bold]Pack:[/] {pack_dict.get('title', pack)}\n"
        f"[bold]Services:[/] {len(services_raw)}\n"
        f"[bold]Target:[/] {target}\n"
        f"[bold]Duration:[/] {duration}s",
        title="[cyan]ITSI Degradation Scenarios[/]",
    ))

    with console.status("[cyan]Claude is generating demo scenarios...[/]"):
        scenarios = generate_scenarios(services=services_summary, context=context)

    if not scenarios:
        console.print("[red]No scenarios generated.[/]")
        sys.exit(1)

    # Print scenario menu
    console.print(f"\n[bold]Generated {len(scenarios)} scenarios:[/]\n")
    table = Table(show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Scenario", style="bold")
    table.add_column("Service")
    table.add_column("Type", style="cyan")
    table.add_column("Severity", style="yellow")
    table.add_column("Alert in")
    for i, sc in enumerate(scenarios, 1):
        sev_color = "red" if sc["severity"] == "critical" else "yellow" if sc["severity"] == "high" else "white"
        table.add_row(
            str(i),
            sc["name"],
            sc["service_name"],
            sc["failure_type"],
            f"[{sev_color}]{sc['severity']}[/]",
            f"~{sc['time_to_alert_seconds']}s",
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
def neap(pack, output, index, context, silence, no_correlation_searches):
    """
    Generate NEAPs + correlation searches for an existing content pack.

    NEAPs (Notable Event Aggregation Policies) are generated from templates — one per
    service, grouping notables into episodes. Correlation searches are AI-generated
    SPL that fire notables into those episodes.

    Output is a separate JSON bundle loaded via the ITSI REST API or packaged into
    a Splunk app alongside the content pack.

    Example:
      python -m itsi_accelerator neap --pack apm_pack.json -o apm_neap_bundle.json
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

    # 3. Serialize
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
