from typing import Optional

import typer

from idlekube.compute import build_output_dict
from idlekube.console import console
from idlekube.formatters.csv_ import write_csv
from idlekube.formatters.html_ import write_html
from idlekube.formatters.json_ import write_json
from idlekube.formatters.report_paths import resolve_report_path
from idlekube.models import NamespaceSummary, WorkloadRow


def cluster_totals(workload_rows: list[WorkloadRow]) -> tuple[int, int, int, int, float]:
    return (
        sum(r.cpu_req for r in workload_rows),
        sum(r.cpu_usage for r in workload_rows),
        sum(r.mem_req for r in workload_rows),
        sum(r.mem_usage for r in workload_rows),
        sum(r.monthly_waste for r in workload_rows),
    )


def write_export_report(
    output_format: str,
    workload_rows: list[WorkloadRow],
    namespace_summary: dict[str, NamespaceSummary],
    cluster_cpu_req: int,
    cluster_cpu_usage: int,
    cluster_mem_req: int,
    cluster_mem_usage: int,
    cluster_waste_usd: float,
    cpu_cost: float,
    memory_cost: float,
    namespace_filter: Optional[str],
    print_stdout: bool,
    cost: bool = False,
) -> None:
    output_data = build_output_dict(
        workload_rows=workload_rows,
        namespace_summary=namespace_summary,
        cluster_cpu_req=cluster_cpu_req,
        cluster_cpu_usage=cluster_cpu_usage,
        cluster_mem_req=cluster_mem_req,
        cluster_mem_usage=cluster_mem_usage,
        cluster_waste_usd=cluster_waste_usd,
        cpu_cost=cpu_cost,
        memory_cost=memory_cost,
        namespace_filter=namespace_filter,
        cost=cost,
    )
    report_path = resolve_report_path(output_format, namespace_filter)
    if output_format == "json":
        write_json(output_data, str(report_path))
    elif output_format == "csv":
        write_csv(output_data, str(report_path))
    else:
        write_html(output_data, str(report_path))
    console.print(f"[green]Report saved:[/green] {report_path}")
    if print_stdout and output_format in ("json", "csv"):
        if output_format == "json":
            write_json(output_data, None)
        else:
            write_csv(output_data, None)


def exit_if_empty_namespace(namespace_filter: Optional[str], workload_rows: list[WorkloadRow]) -> None:
    if namespace_filter and not workload_rows:
        console.print(
            f"[yellow]No deployments found in namespace '{namespace_filter}'.[/yellow]"
        )
        raise typer.Exit(code=0)
