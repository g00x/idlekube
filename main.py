# idlekube is an experimental Kubernetes efficiency scanner.
# It uses current metrics-server data, so recommendations should be validated
# against historical usage before changing production requests.

from typing import Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from rich.console import Console
import typer

import idlekube.console as console_module
from idlekube.console import console
from idlekube.compute import run_scan
from idlekube.formatters.table import render_table_output
from idlekube.k8s import get_pod_metrics
from idlekube.scan_output import (
    cluster_totals,
    exit_if_empty_namespace,
    write_export_report,
)

app = typer.Typer(help="IdleKube — Kubernetes efficiency scanner.")
EXPORT_FORMATS = ("json", "csv", "html")


@app.callback()
def main() -> None:
    """Analyze cluster resource usage and surface optimization targets."""


@app.command()
def scan(
    namespace_filter: Optional[str] = typer.Option(
        None, "--namespace", "-n", help="Analyze only this namespace (e.g. payments)"
    ),
    cpu_cost: float = typer.Option(25.0, help="Monthly cost per CPU core"),
    memory_cost: float = typer.Option(4.0, help="Monthly cost per GB memory"),
    output_format: str = typer.Option("table", "--format", help="Output format: table, json, csv, html"),
    print_stdout: bool = typer.Option(
        False, "--stdout", help="Also print JSON/CSV to stdout (for jq). Ignored for HTML."
    ),
):
    if output_format not in ("table",) + EXPORT_FORMATS:
        Console(stderr=True).print(
            f"[red]Invalid format: {output_format}. Use table, json, csv, or html.[/red]"
        )
        raise typer.Exit(code=1)
    if output_format == "html" and print_stdout:
        Console(stderr=True).print(
            "[red]--stdout is not supported for HTML. HTML is always saved under reports/.[/red]"
        )
        raise typer.Exit(code=1)
    if output_format in EXPORT_FORMATS:
        console_module.console = Console(stderr=True)

    config.load_kube_config()
    apps_v1, core_v1 = client.AppsV1Api(), client.CoreV1Api()
    if namespace_filter is not None:
        try:
            core_v1.read_namespace(namespace_filter)
        except ApiException as e:
            if e.status == 404:
                console.print(f"[red]Namespace not found: {namespace_filter}[/red]")
                raise typer.Exit(code=1)
            raise

    pod_metrics = get_pod_metrics(namespace_filter)
    if namespace_filter is not None:
        deployments = apps_v1.list_namespaced_deployment(namespace_filter)
        pods = core_v1.list_namespaced_pod(namespace_filter)
    else:
        deployments = apps_v1.list_deployment_for_all_namespaces()
        pods = core_v1.list_pod_for_all_namespaces()

    workload_rows, namespace_summary = run_scan(
        deployments, pods, pod_metrics, namespace_filter, cpu_cost, memory_cost
    )
    totals = cluster_totals(workload_rows)

    if output_format in EXPORT_FORMATS:
        write_export_report(
            output_format, workload_rows, namespace_summary, *totals,
            cpu_cost, memory_cost, namespace_filter, print_stdout,
        )
        return

    exit_if_empty_namespace(namespace_filter, workload_rows)
    render_table_output(
        workload_rows, namespace_summary, *totals, cpu_cost, memory_cost, namespace_filter
    )


if __name__ == "__main__":
    import sys

    # `python3 main.py` → same as `python3 main.py scan`
    if len(sys.argv) == 1:
        sys.argv.append("scan")
    app()
