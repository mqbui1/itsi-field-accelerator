"""
Degradation scenario executor.

Runs inject → wait → recover for a single scenario.
Supports three targets:
  simulate   — dry-run, prints what would happen (default, safe)
  k8s        — executes kubectl commands
  hec        — sends events to Splunk HEC
  otel-demo  — toggles OpenTelemetry Demo feature flags
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

# Shared state file — read by probe checker
SCENARIO_STATE_FILE = Path.home() / ".itsi_accelerator_state.json"


def _write_state(scenario: dict, duration: int) -> None:
    state = {
        "active": True,
        "scenario_name": scenario.get("name", ""),
        "service_name": scenario.get("service_name", ""),
        "failure_type": scenario.get("failure_type", ""),
        "injected_at": time.time(),
        "recover_at": time.time() + duration,
    }
    SCENARIO_STATE_FILE.write_text(json.dumps(state, indent=2))


def _clear_state() -> None:
    state = {"active": False}
    SCENARIO_STATE_FILE.write_text(json.dumps(state))


# ── kubectl helpers ───────────────────────────────────────────────────────────

def _kubectl(
    cmd: str,
    namespace: str,
    kubeconfig: str,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Run a kubectl command with namespace and kubeconfig substituted.
    Returns (success, output).
    """
    filled = (
        cmd
        .replace("{namespace}", namespace)
        .replace("{kubeconfig}", kubeconfig)
    )
    tokens = filled.split()
    # Strip leading "kubectl" from the command string — we'll prepend it ourselves
    if tokens and tokens[0] == "kubectl":
        tokens = tokens[1:]
    parts = ["kubectl", "--kubeconfig", kubeconfig] + tokens

    if dry_run:
        return True, f"[dry-run] {' '.join(parts)}"

    result = subprocess.run(parts, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    return result.returncode == 0, output.strip()


# ── HEC helpers ───────────────────────────────────────────────────────────────

def _send_hec_events(
    hec_url: str,
    hec_token: str,
    events: list[dict],
    dry_run: bool = False,
) -> tuple[bool, str]:
    if dry_run:
        return True, f"[dry-run] Would POST {len(events)} events to {hec_url}"

    headers = {"Authorization": f"Splunk {hec_token}", "Content-Type": "application/json"}
    batch = "\n".join(json.dumps(e) for e in events)
    try:
        resp = requests.post(
            f"{hec_url.rstrip('/')}/services/collector/event",
            headers=headers,
            data=batch,
            timeout=10,
        )
        return resp.ok, f"HEC status {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


# ── OTel Demo feature flag helpers ────────────────────────────────────────────

def _set_otel_demo_flag(
    featureflag_url: str,
    flag_name: str,
    enabled: bool,
    dry_run: bool = False,
) -> tuple[bool, str]:
    if not flag_name:
        return True, "no feature flag configured for this scenario"
    if dry_run:
        action = "enable" if enabled else "disable"
        return True, f"[dry-run] Would {action} OTel demo flag '{flag_name}' at {featureflag_url}"

    try:
        resp = requests.post(
            f"{featureflag_url.rstrip('/')}/feature-flag",
            json={"name": flag_name, "enabled": enabled},
            timeout=10,
        )
        return resp.ok, f"Flag '{flag_name}' {'enabled' if enabled else 'disabled'}: {resp.status_code}"
    except Exception as e:
        return False, str(e)


# ── Main executor ─────────────────────────────────────────────────────────────

def run_scenario(
    scenario: dict[str, Any],
    target: str = "simulate",
    duration: int = 300,
    namespace: str = "default",
    kubeconfig: str = "~/.kube/config",
    hec_url: str = "",
    hec_token: str = "",
    featureflag_url: str = "http://localhost:8013",
    print_fn=print,
) -> bool:
    """
    Execute a single degradation scenario end-to-end.

    Args:
        scenario: Scenario dict from scenario_generator.generate_scenarios()
        target: "simulate" | "k8s" | "hec" | "otel-demo"
        duration: Seconds to hold the degradation before recovering
        namespace: K8s namespace (used for k8s target)
        kubeconfig: Path to kubeconfig file (used for k8s target)
        hec_url: Splunk HEC URL (used for hec target)
        hec_token: Splunk HEC token (used for hec target)
        featureflag_url: OTel demo feature flag service URL
        print_fn: Callable for output (allows rich console injection)

    Returns:
        True if inject + recover both succeeded, False otherwise.
    """
    dry_run = (target == "simulate")
    name = scenario.get("name", "Unknown scenario")

    print_fn(f"\n[bold]Injecting:[/] {name}")
    print_fn(f"[dim]{scenario.get('description', '')}[/]")
    print_fn(f"\n[bold]Expected impact:[/] {scenario.get('expected_impact', '')}")
    print_fn(f"[bold]Time to alert:[/] ~{scenario.get('time_to_alert_seconds', '?')}s")

    if scenario.get("demo_talking_points"):
        print_fn("\n[bold]Talking points:[/]")
        for point in scenario["demo_talking_points"]:
            print_fn(f"  • {point}")

    # ── INJECT ────────────────────────────────────────────────────────────────
    if not dry_run:
        _write_state(scenario, duration)
    print_fn("\n[cyan]--- INJECT ---[/]")
    inject_ok = True

    if target in ("k8s", "simulate"):
        for cmd in scenario.get("k8s_inject", []):
            ok, out = _kubectl(cmd, namespace=namespace, kubeconfig=kubeconfig, dry_run=dry_run)
            icon = "[green]✓[/]" if ok else "[red]✗[/]"
            print_fn(f"  {icon} {cmd.replace('{namespace}', namespace)}")
            if out and out != cmd:
                print_fn(f"     [dim]{out}[/]")
            if not ok:
                inject_ok = False

    if target in ("hec", "simulate") and scenario.get("hec_events"):
        ok, msg = _send_hec_events(
            hec_url=hec_url,
            hec_token=hec_token,
            events=scenario["hec_events"],
            dry_run=dry_run,
        )
        icon = "[green]✓[/]" if ok else "[red]✗[/]"
        print_fn(f"  {icon} HEC: {msg}")
        if not ok:
            inject_ok = False

    if target in ("otel-demo", "simulate") and scenario.get("otel_demo_flag"):
        ok, msg = _set_otel_demo_flag(
            featureflag_url=featureflag_url,
            flag_name=scenario["otel_demo_flag"],
            enabled=True,
            dry_run=dry_run,
        )
        icon = "[green]✓[/]" if ok else "[red]✗[/]"
        print_fn(f"  {icon} Feature flag: {msg}")
        if not ok:
            inject_ok = False

    if not inject_ok:
        print_fn("\n[red]Injection had errors — check output above. Attempting recovery anyway.[/]")

    # ── WAIT ──────────────────────────────────────────────────────────────────
    if dry_run:
        print_fn(f"\n[dim]  [simulate] Would hold degradation for {duration}s then recover.[/]")
    else:
        print_fn(f"\n[yellow]Holding degradation for {duration}s... (Ctrl+C to recover early)[/]")
        try:
            for remaining in range(duration, 0, -10):
                time.sleep(min(10, remaining))
                if remaining % 60 == 0 or remaining <= 30:
                    print_fn(f"  [dim]{remaining}s remaining...[/]")
        except KeyboardInterrupt:
            print_fn("\n[yellow]Interrupted — recovering now.[/]")

    # ── RECOVER ───────────────────────────────────────────────────────────────
    print_fn("\n[cyan]--- RECOVER ---[/]")
    recover_ok = True

    if target in ("k8s", "simulate"):
        for cmd in scenario.get("k8s_recover", []):
            ok, out = _kubectl(cmd, namespace=namespace, kubeconfig=kubeconfig, dry_run=dry_run)
            icon = "[green]✓[/]" if ok else "[red]✗[/]"
            print_fn(f"  {icon} {cmd.replace('{namespace}', namespace)}")
            if out and out != cmd:
                print_fn(f"     [dim]{out}[/]")
            if not ok:
                recover_ok = False

    if target in ("otel-demo", "simulate") and scenario.get("otel_demo_flag"):
        ok, msg = _set_otel_demo_flag(
            featureflag_url=featureflag_url,
            flag_name=scenario["otel_demo_flag"],
            enabled=False,
            dry_run=dry_run,
        )
        icon = "[green]✓[/]" if ok else "[red]✗[/]"
        print_fn(f"  {icon} Feature flag: {msg}")
        if not ok:
            recover_ok = False

    if not dry_run:
        _clear_state()
    status = "[green]Recovery complete[/]" if recover_ok else "[yellow]Recovery had errors — manual cleanup may be needed[/]"
    print_fn(f"\n{status}")
    return inject_ok and recover_ok
