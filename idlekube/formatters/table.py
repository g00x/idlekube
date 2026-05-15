from typing import Optional

from rich.panel import Panel
from rich.table import Table

from idlekube.console import console
from idlekube.insights import (
    build_executive_summary,
    category_counts,
    recommended_action_order,
    top_unowned_waste,
)
from idlekube.models import ExecutiveSummary, NamespaceSummary, WorkloadRow

MAX_NS_ROWS = 8
MAX_WL_ROWS = 12
MAX_ADVISOR = 5


def _money(amount: float) -> str:
    return f"${amount:,.0f}"


def _badge(level: str) -> str:
    colors = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
    c = colors.get(level, "white")
    return f"[{c}]{level}[/{c}]"


def _render_executive_summary(
    workload_rows: list[WorkloadRow],
    namespace_summary: dict[str, NamespaceSummary],
    cluster_waste_usd: float,
    namespace_filter: Optional[str],
) -> ExecutiveSummary:
    ex = build_executive_summary(workload_rows, namespace_summary, cluster_waste_usd)
    scope = f"namespace {namespace_filter}" if namespace_filter else "cluster"
    lines = [
        f"Scope: [cyan]{scope}[/cyan]",
        f"Potential annual savings: [bold red]{_money(ex.annual_waste)}[/bold red]  "
        f"([dim]{_money(ex.monthly_waste)}/mo[/dim])",
        f"Highest-waste namespace: [yellow]{ex.top_namespace}[/yellow] → "
        f"{_money(ex.top_namespace_annual)}/year",
        f"Most overprovisioned workload: [yellow]{ex.top_workload_ref}[/yellow] → "
        f"{_money(ex.top_workload_annual)}/year",
        f"Ownership coverage: [cyan]{ex.ownership_coverage_pct}%[/cyan]  ·  "
        f"High-priority targets: [red]{ex.high_priority_count}[/red] / {ex.workload_count} workloads",
    ]
    if not ex.trends_available:
        lines.append(
            "[dim]Trends: unavailable (connect Prometheus for 7–30d waste & efficiency trends)[/dim]"
        )
    console.print(Panel("\n".join(lines), title="[bold]Executive Summary[/bold]", border_style="blue"))
    return ex


def _render_recommended_order(workload_rows: list[WorkloadRow]) -> None:
    order = recommended_action_order(workload_rows, limit=5)
    if not order:
        return
    console.print("\n[bold]What should I do first?[/bold]\n")
    for i, row in enumerate(order, 1):
        cats = ", ".join(row.categories)
        console.print(
            f"  {i}. [bold]{row.namespace}/{row.name}[/bold]\n"
            f"     Potential annual savings: {_money(row.annual_waste)}  ·  "
            f"Risk: {_badge(row.risk_level)}  ·  Confidence: {_badge(row.confidence_level)}\n"
            f"     Categories: [dim]{cats}[/dim]"
        )


def _render_unowned_waste(workload_rows: list[WorkloadRow]) -> None:
    unowned = top_unowned_waste(workload_rows, limit=5)
    if not unowned:
        return
    console.print("\n[bold]Top unowned waste[/bold]  [dim](add owner/team labels)[/dim]\n")
    for row in unowned:
        console.print(
            f"  • {row.namespace}/{row.name} → {_money(row.annual_waste)}/year  "
            f"[dim](owner missing)[/dim]"
        )


def _render_categories(workload_rows: list[WorkloadRow]) -> None:
    counts = category_counts(workload_rows)
    if not counts:
        return
    parts = [f"{k}: {v}" for k, v in counts.items()]
    console.print("\n[bold]Optimization categories[/bold]  " + "  ·  ".join(parts))


def _render_namespace_table(namespace_summary: dict[str, NamespaceSummary]) -> None:
    if not namespace_summary:
        return
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
    console.print(table)


def _render_workload_table(workload_rows: list[WorkloadRow]) -> None:
    if not workload_rows:
        return
    table = Table(title=f"Top workloads by annual waste (showing {min(len(workload_rows), MAX_WL_ROWS)})")
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
            ", ".join(row.categories),
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
        "\n[bold]Suggested safe review targets[/bold]  "
        "[dim](conservative — validate before applying)[/dim]\n"
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
        for reason in rec.confidence_reasons[:3]:
            console.print(f"      [dim]• {reason}[/dim]")
        console.print(f"      [dim]{rec.note}[/dim]\n")


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
    title = "IdleKube — Kubernetes Cost & Waste Intelligence"
    if namespace_filter:
        title += f" · {namespace_filter}"
    console.print(f"\n[bold cyan]{title}[/bold cyan]\n")

    _render_executive_summary(
        workload_rows, namespace_summary, cluster_waste_usd, namespace_filter
    )
    _render_recommended_order(workload_rows)
    _render_unowned_waste(workload_rows)
    _render_categories(workload_rows)
    _render_namespace_table(namespace_summary)
    _render_workload_table(workload_rows)
    _render_advisor_targets(workload_rows)

    cpu_eff = round((cluster_cpu_usage / cluster_cpu_req) * 100, 1) if cluster_cpu_req else 0
    mem_eff = round((cluster_mem_usage / cluster_mem_req) * 100, 1) if cluster_mem_req else 0
    console.print(
        f"\n[dim]Efficiency snapshot: CPU {cpu_eff}% · Memory {mem_eff}% · "
        f"Cost model ${_money(cpu_cost)}/core/mo · ${_money(memory_cost)}/GB/mo · "
        f"Snapshot-only — not a billing system.[/dim]\n"
    )
