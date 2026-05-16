from typing import Optional

from rich.panel import Panel
from rich.table import Table

from idlekube.console import console
from idlekube.insights import (
    build_executive_summary,
    category_counts,
    recommended_action_order,
    sort_categories,
    top_unowned_waste,
)
from idlekube.models import ExecutiveSummary, NamespaceSummary, WorkloadRow
from idlekube.recommendations import CONFIDENCE_REASONS, VALIDATION_NOTE

MAX_NS_ROWS = 8
MAX_WL_ROWS = 12
MAX_ADVISOR = 5


def _money(amount: float) -> str:
    return f"${amount:,.0f}"


def _usd_rate(amount: float) -> str:
    return f"${amount:.0f}"


def _badge(level: str) -> str:
    colors = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
    c = colors.get(level, "white")
    return f"[{c}]{level}[/{c}]"


def _format_categories(categories: list[str]) -> str:
    return ", ".join(sort_categories(categories))


def _render_executive_summary(
    workload_rows: list[WorkloadRow],
    namespace_summary: dict[str, NamespaceSummary],
    cluster_waste_usd: float,
    namespace_filter: Optional[str],
    cost: bool,
) -> ExecutiveSummary:
    ex = build_executive_summary(workload_rows, namespace_summary, cluster_waste_usd)
    scope = f"namespace {namespace_filter}" if namespace_filter else "cluster"
    lines = [f"Scope: [cyan]{scope}[/cyan]"]
    if cost:
        lines.extend(
            [
                f"Potential annual savings: [bold red]{_money(ex.annual_waste)}[/bold red]  "
                f"([dim]{_money(ex.monthly_waste)}/mo[/dim])",
                f"Highest optimization opportunity: [yellow]{ex.top_namespace}[/yellow] → "
                f"{_money(ex.top_namespace_annual)}/year",
                f"Highest optimization target: [yellow]{ex.top_workload_ref}[/yellow] → "
                f"{_money(ex.top_workload_annual)}/year",
            ]
        )
    lines.append(
        f"Ownership coverage: [cyan]{ex.ownership_coverage_pct}%[/cyan]  ·  "
        f"High-priority targets: [red]{ex.high_priority_count}[/red] / {ex.workload_count} workloads"
    )
    console.print(Panel("\n".join(lines), title="[bold]Executive Summary[/bold]", border_style="blue"))
    console.print(
        "[dim]Snapshot-based analysis using metrics-server. "
        "Historical utilization trends unavailable.[/dim]\n"
    )
    return ex


def _render_recommended_order(workload_rows: list[WorkloadRow], cost: bool) -> None:
    order = recommended_action_order(workload_rows, limit=5)
    if not order:
        return
    console.print("\n[bold]What should I do first?[/bold]\n")
    for i, row in enumerate(order, 1):
        console.print(f"  {i}. [bold]{row.namespace}/{row.name}[/bold]")
        if cost:
            console.print(f"     Savings: {_money(row.annual_waste)}/year")
        else:
            console.print(
                f"     Priority: {_badge(row.priority)}  ·  "
                f"CPU unused: {row.unused_cpu}m  ·  Mem unused: {row.unused_mem}Mi"
            )
        console.print(f"     Risk: {_badge(row.risk_level)}")
        console.print(f"     Confidence: {_badge(row.confidence_level)}")
        console.print(f"     Categories: [dim]{_format_categories(row.categories)}[/dim]")


def _render_unowned_waste(workload_rows: list[WorkloadRow], cost: bool) -> None:
    unowned = top_unowned_waste(workload_rows, limit=5)
    if not unowned:
        return
    console.print("\n[bold]Top unowned workloads[/bold]  [dim](add owner/team labels)[/dim]\n")
    for row in unowned:
        if cost:
            console.print(
                f"  • {row.namespace}/{row.name} → {_money(row.annual_waste)}/year  "
                f"[dim](owner missing)[/dim]"
            )
        else:
            console.print(
                f"  • {row.namespace}/{row.name}  "
                f"[dim]CPU unused: {row.unused_cpu}m · Mem unused: {row.unused_mem}Mi · "
                f"(owner missing)[/dim]"
            )


def _render_categories(workload_rows: list[WorkloadRow]) -> None:
    counts = category_counts(workload_rows)
    if not counts:
        return
    parts = [f"{k}: {v}" for k, v in counts.items()]
    console.print("\n[bold]Optimization categories[/bold]  " + "  ·  ".join(parts))


def _render_namespace_table(namespace_summary: dict[str, NamespaceSummary], cost: bool) -> None:
    if not namespace_summary:
        return
    if cost:
        table = Table(title="Namespace waste (annual)", show_lines=False)
        table.add_column("Namespace")
        table.add_column("Annual waste", justify="right")
        table.add_column("Workloads", justify="right")
        table.add_column("High", justify="right")
        for namespace, data in sorted(
            namespace_summary.items(), key=lambda x: x[1].waste_usd, reverse=True
        )[:MAX_NS_ROWS]:
            table.add_row(
                namespace,
                _money(data.annual_waste),
                str(data.workloads),
                str(data.high),
            )
    else:
        table = Table(title="Namespace inefficiency", show_lines=False)
        table.add_column("Namespace")
        table.add_column("CPU unused", justify="right")
        table.add_column("Mem unused", justify="right")
        table.add_column("Workloads", justify="right")
        table.add_column("High", justify="right")
        for namespace, data in sorted(
            namespace_summary.items(), key=lambda x: x[1].waste_usd, reverse=True
        )[:MAX_NS_ROWS]:
            cpu_unused = max(data.cpu_req - data.cpu_usage, 0)
            mem_unused = max(data.mem_req - data.mem_usage, 0)
            table.add_row(
                namespace,
                f"{cpu_unused}m",
                f"{mem_unused}Mi",
                str(data.workloads),
                str(data.high),
            )
    console.print(table)


def _render_workload_table(workload_rows: list[WorkloadRow], cost: bool) -> None:
    if not workload_rows:
        return
    shown = min(len(workload_rows), MAX_WL_ROWS)
    if cost:
        table = Table(title=f"Top workloads by annual waste (showing {shown})")
        table.add_column("Workload")
        table.add_column("Annual", justify="right")
        table.add_column("Categories")
        table.add_column("Risk")
        table.add_column("Owner")
        for row in workload_rows[:MAX_WL_ROWS]:
            owner = row.owner if row.owner != "unknown" else "[dim]unowned[/dim]"
            table.add_row(
                f"{row.namespace}/{row.name}",
                _money(row.annual_waste),
                _format_categories(row.categories),
                row.risk_level,
                owner,
            )
    else:
        table = Table(title=f"Top workloads by inefficiency (showing {shown})")
        table.add_column("Workload")
        table.add_column("Priority")
        table.add_column("CPU unused", justify="right")
        table.add_column("Mem unused", justify="right")
        table.add_column("Categories")
        table.add_column("Risk")
        table.add_column("Owner")
        for row in workload_rows[:MAX_WL_ROWS]:
            owner = row.owner if row.owner != "unknown" else "[dim]unowned[/dim]"
            table.add_row(
                f"{row.namespace}/{row.name}",
                row.priority,
                f"{row.unused_cpu}m",
                f"{row.unused_mem}Mi",
                _format_categories(row.categories),
                row.risk_level,
                owner,
            )
    console.print(table)


def _render_advisor_targets(workload_rows: list[WorkloadRow]) -> None:
    rows = [r for r in workload_rows if r.recommendation is not None]
    rows.sort(key=lambda r: r.annual_waste, reverse=True)
    if not rows:
        return

    console.print(
        "\n[bold]Suggested review targets[/bold]  "
        "[dim](snapshot-based, low confidence)[/dim]\n"
    )
    for row in rows[:MAX_ADVISOR]:
        rec = row.recommendation
        if rec is None:
            continue
        console.print(f"  [bold]{row.namespace}/{row.name}[/bold]")
        if rec.suggested_cpu_request_m != row.cpu_req:
            console.print(
                f"    CPU    request: {row.cpu_req}m → {rec.suggested_cpu_request_m}m  ·  "
                f"observed: ~{rec.observed_cpu_m}m  ·  limit target: {rec.suggested_cpu_limit_m}m"
            )
        else:
            console.print(f"    CPU    request looks reasonable (observed ~{rec.observed_cpu_m}m)")
        if rec.suggested_memory_request_mib != row.mem_req:
            console.print(
                f"    Memory request: {row.mem_req}Mi → {rec.suggested_memory_request_mib}Mi  ·  "
                f"observed: ~{rec.observed_memory_mib}Mi  ·  limit target: {rec.suggested_memory_limit_mib}Mi"
            )
        console.print(
            f"    Confidence: {_badge(rec.confidence)}  ·  Risk: {_badge(row.risk_level)}"
        )
        for reason in CONFIDENCE_REASONS[:2]:
            console.print(f"      [dim]• {reason}[/dim]")
        console.print(f"      [dim]{VALIDATION_NOTE}[/dim]\n")


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
    cost: bool = False,
) -> None:
    title = "IdleKube — Kubernetes Cost & Waste Intelligence"
    if namespace_filter:
        title += f" · {namespace_filter}"
    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    _render_executive_summary(
        workload_rows, namespace_summary, cluster_waste_usd, namespace_filter, cost
    )
    _render_recommended_order(workload_rows, cost)
    _render_unowned_waste(workload_rows, cost)
    _render_categories(workload_rows)
    _render_namespace_table(namespace_summary, cost)
    _render_workload_table(workload_rows, cost)
    _render_advisor_targets(workload_rows)

    cpu_eff = round((cluster_cpu_usage / cluster_cpu_req) * 100, 1) if cluster_cpu_req else 0
    mem_eff = round((cluster_mem_usage / cluster_mem_req) * 100, 1) if cluster_mem_req else 0
    if cost:
        console.print(
            f"\n[dim]Efficiency snapshot: CPU {cpu_eff}% · Memory {mem_eff}% · "
            f"Cost model {_usd_rate(cpu_cost)}/core/mo · {_usd_rate(memory_cost)}/GB/mo · "
            f"Snapshot-only — not a billing system.[/dim]\n"
        )
    else:
        console.print(
            f"\n[dim]Efficiency snapshot: CPU {cpu_eff}% · Memory {mem_eff}% · "
            f"Snapshot-only — not a billing system.[/dim]\n"
        )
