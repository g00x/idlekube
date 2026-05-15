from typing import Optional

from rich.panel import Panel
from rich.table import Table

from idlekube.compute import colored_priority
from idlekube.console import console
from idlekube.models import NamespaceSummary, WorkloadRow


def _format_cpu_line(row: WorkloadRow) -> str | None:
    rec = row.recommendation
    if rec is None:
        return None

    if rec.suggested_cpu_request_m == row.cpu_req:
        return (
            f"    cpu:    ✓ request looks reasonable  "
            f"(usage: {row.cpu_usage}m / request: {row.cpu_req}m = {row.cpu_ratio}%)"
        )

    return (
        f"    cpu:    request {row.cpu_req:>5}m → {rec.suggested_cpu_request_m:>5}m    "
        f"limit → {rec.suggested_cpu_limit_m:>5}m    "
        f"(current usage: {row.cpu_usage}m)"
    )


def _format_memory_line(row: WorkloadRow) -> str | None:
    rec = row.recommendation
    if rec is None:
        return None

    if rec.suggested_memory_request_mib == row.mem_req:
        return (
            f"    memory: ✓ request looks reasonable  "
            f"(usage: {row.mem_usage}Mi / request: {row.mem_req}Mi = {row.mem_ratio}%)"
        )

    return (
        f"    memory: request {row.mem_req:>5}Mi → {rec.suggested_memory_request_mib:>5}Mi   "
        f"limit → {rec.suggested_memory_limit_mib:>5}Mi   "
        f"(current usage: {row.mem_usage}Mi)"
    )


def _render_resource_recommendations(workload_rows: list[WorkloadRow]) -> None:
    rows_with_rec = [r for r in workload_rows if r.recommendation is not None]
    if not rows_with_rec:
        return

    console.print(
        "\n[bold magenta]Suggested resource values[/bold magenta]  "
        "[dim](snapshot estimate — validate before applying)[/dim]\n"
    )

    sorted_rows = sorted(rows_with_rec, key=lambda r: r.monthly_waste, reverse=True)
    shown = 0
    for row in sorted_rows:
        if shown >= 10:
            break

        cpu_line = _format_cpu_line(row)
        mem_line = _format_memory_line(row)
        if cpu_line is None and mem_line is None:
            continue
        if (
            row.recommendation
            and row.recommendation.suggested_cpu_request_m == row.cpu_req
            and row.recommendation.suggested_memory_request_mib == row.mem_req
        ):
            continue

        console.print(f"  {row.namespace}/{row.name}")
        if cpu_line:
            console.print(cpu_line)
        if mem_line:
            console.print(mem_line)
        shown += 1

    console.print(
        "\n  [dim]These values are based on current metrics-server snapshot data.[/dim]\n"
        "  [dim]For production workloads, validate against p95 usage over 7–30 days[/dim]\n"
        "  [dim]before modifying requests or limits.[/dim]"
    )


def render_table_output(
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
) -> None:
    unused_cpu_total = max(cluster_cpu_req - cluster_cpu_usage, 0)
    unused_mem_total = max(cluster_mem_req - cluster_mem_usage, 0)

    cpu_efficiency = (
        round((cluster_cpu_usage / cluster_cpu_req) * 100, 2) if cluster_cpu_req else 0
    )
    memory_efficiency = (
        round((cluster_mem_usage / cluster_mem_req) * 100, 2) if cluster_mem_req else 0
    )

    scope_title = (
        f"Namespace Summary: {namespace_filter}"
        if namespace_filter
        else "Cluster Summary"
    )
    panel_title = f"idlekube — {namespace_filter}" if namespace_filter else "idlekube"

    summary = (
        f"[bold]{scope_title}[/bold]\n\n"
        f"CPU requested: [yellow]{cluster_cpu_req}m[/yellow]\n"
        f"CPU used: [green]{cluster_cpu_usage}m[/green]\n"
        f"Potentially unused CPU: [red]{unused_cpu_total}m[/red]\n"
        f"CPU efficiency: [cyan]{cpu_efficiency}%[/cyan]\n\n"
        f"Memory requested: [yellow]{cluster_mem_req}Mi[/yellow]\n"
        f"Memory used: [green]{cluster_mem_usage}Mi[/green]\n"
        f"Potentially unused memory: [red]{unused_mem_total}Mi[/red]\n"
        f"Memory efficiency: [cyan]{memory_efficiency}%[/cyan]\n\n"
        f"Estimated monthly optimization potential: [bold red]${round(cluster_waste_usd, 2)}[/bold red]\n"
        f"Estimated annual optimization potential: [bold red]${round(cluster_waste_usd * 12, 2)}[/bold red]\n\n"
        f"Pricing model: ${cpu_cost}/CPU core/month, "
        f"${memory_cost}/GB memory/month"
    )

    console.print(Panel(summary, title=panel_title))

    ns_table = Table(title="Namespace Summary")

    ns_table.add_column("Namespace")
    ns_table.add_column("Workloads")
    ns_table.add_column("Owners")
    ns_table.add_column("CPU Req")
    ns_table.add_column("Pot. unused CPU")
    ns_table.add_column("Mem Req")
    ns_table.add_column("Pot. unused Mem")
    ns_table.add_column("Est. potential/mo")
    ns_table.add_column("High")
    ns_table.add_column("Medium")

    sorted_namespaces = sorted(
        namespace_summary.items(),
        key=lambda item: item[1].waste_usd,
        reverse=True,
    )

    for namespace, data in sorted_namespaces:
        ns_unused_cpu = max(data.cpu_req - data.cpu_usage, 0)
        ns_unused_mem = max(data.mem_req - data.mem_usage, 0)
        owners = ", ".join(sorted(data.owners))

        ns_table.add_row(
            namespace,
            str(data.workloads),
            owners,
            f"{data.cpu_req}m",
            f"{ns_unused_cpu}m",
            f"{data.mem_req}Mi",
            f"{ns_unused_mem}Mi",
            f"${round(data.waste_usd, 2)}",
            str(data.high),
            str(data.medium),
        )

    console.print(ns_table)

    workload_table = Table(title="Workload Optimization Priorities")

    workload_table.add_column("Namespace")
    workload_table.add_column("Deployment")
    workload_table.add_column("Owner")
    workload_table.add_column("CPU Req")
    workload_table.add_column("CPU Usage")
    workload_table.add_column("Pot. unused CPU")
    workload_table.add_column("Mem Req")
    workload_table.add_column("Mem Usage")
    workload_table.add_column("Pot. unused Mem")
    workload_table.add_column("Est. potential/mo")
    workload_table.add_column("Priority")
    workload_table.add_column("Problems")

    optimization_targets = []

    for row in workload_rows:
        workload_table.add_row(
            row.namespace,
            row.name,
            row.owner,
            f"{row.cpu_req}m",
            f"{row.cpu_usage}m",
            f"{row.unused_cpu}m",
            f"{row.mem_req}Mi",
            f"{row.mem_usage}Mi",
            f"{row.unused_mem}Mi",
            f"${row.monthly_waste}",
            colored_priority(row.priority),
            ", ".join(row.problems) if row.problems else "OK",
        )

        if row.priority in ["HIGH", "MEDIUM"]:
            optimization_targets.append(row)

    console.print(workload_table)

    console.print("\n[bold magenta]Top Optimization Targets[/bold magenta]\n")

    if optimization_targets:
        for row in optimization_targets[:10]:
            color = "red" if row.priority == "HIGH" else "yellow"
            console.print(
                f"• [{color}]{row.namespace}/{row.name}[/{color}]"
                f" — {row.priority} priority, estimated optimization potential ${row.monthly_waste}/mo. "
                f"Owner: {row.owner}. "
                f"Potentially unused CPU: {row.unused_cpu}m, potentially unused memory: {row.unused_mem}Mi. "
                f"Reason: {', '.join(row.problems)}."
            )
    else:
        console.print("[green]No recommendations[/green]")

    _render_resource_recommendations(workload_rows)

    console.print("\n[bold cyan]Suggested Next Actions[/bold cyan]\n")

    high_targets = [row for row in workload_rows if row.priority == "HIGH"]
    unknown_owner_targets = [row for row in workload_rows if row.owner == "unknown"]

    if high_targets:
        console.print(
            "1. Start with HIGH priority workloads with the highest estimated monthly optimization potential."
        )
        console.print("2. Validate usage over a longer window before changing production requests.")
        console.print(
            "3. For low utilization workloads, check whether they can be scaled down, removed, or converted to CronJobs."
        )
        console.print("4. For memory-heavy workloads, review p95/p99 memory usage before lowering requests.")
    else:
        console.print("1. No HIGH priority workloads found. Review MEDIUM items first.")

    if unknown_owner_targets:
        console.print(
            f"5. Add ownership labels to {len(unknown_owner_targets)} workload(s), "
            "for example: owner, team, service, environment."
        )

    console.print("\n[bold cyan]How to improve ownership data[/bold cyan]\n")
    console.print(
        "Add labels like:\n"
        "  owner: platform-team\n"
        "  team: backend\n"
        "  service: payment-api\n"
        "  environment: dev"
    )

    console.print("\n[bold cyan]Important note[/bold cyan]\n")
    console.print(
        "This is a snapshot estimate based on current metrics-server data. "
        "Use it for prioritization, not final billing. "
        "For production-grade accuracy, add Prometheus history or OpenCost later."
    )
