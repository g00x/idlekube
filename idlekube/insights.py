"""Cost & waste intelligence: categories, risk, confidence, executive summary."""

from __future__ import annotations

from idlekube.models import ExecutiveSummary, NamespaceSummary, WorkloadRow

PRODUCTION_ENVS = frozenset({"prod", "production", "live", "prd"})
PRODUCTION_NS_HINTS = ("prod", "production", "live")


def annual_usd(monthly: float) -> float:
    return round(monthly * 12, 2)


def is_production(row: WorkloadRow) -> bool:
    env = (row.environment or "").lower()
    if env in PRODUCTION_ENVS:
        return True
    ns = row.namespace.lower()
    return any(hint in ns for hint in PRODUCTION_NS_HINTS)


def classify_categories(row: WorkloadRow) -> list[str]:
    categories: list[str] = []
    if row.replicas == 0:
        categories.append("ZOMBIE_WORKLOAD")
    if row.idle:
        categories.append("IDLE")
    if (row.cpu_req > 0 and row.cpu_ratio < 10) or (row.mem_req > 0 and row.mem_ratio < 25):
        categories.append("OVERPROVISIONED")
    if row.missing_limits:
        categories.append("MISSING_LIMITS")
    if row.owner == "unknown":
        categories.append("NO_OWNER")
    if row.cpu_usage == 0 and row.mem_usage == 0 and row.replicas > 0 and row.cpu_req > 0:
        if "ZOMBIE_WORKLOAD" not in categories:
            categories.append("ZOMBIE_WORKLOAD")
    return categories or ["STABLE"]


def assess_risk(row: WorkloadRow) -> tuple[str, list[str]]:
    reasons: list[str] = []
    score = 0

    if is_production(row):
        reasons.append("production namespace or environment")
        score += 2

    if row.replicas <= 1 and row.replicas > 0:
        reasons.append("single replica — limited blast-radius isolation")
        score += 1

    if row.mem_ratio >= 75 or row.cpu_ratio >= 75:
        reasons.append("high utilization in snapshot — little headroom to cut requests")
        score += 3
    elif row.mem_ratio >= 55:
        reasons.append("elevated memory utilization in snapshot")
        score += 1

    if row.cpu_usage == 0 and row.mem_usage == 0 and row.cpu_req > 0:
        reasons.append("no live usage observed — higher uncertainty")
        score += 1

    if row.idle and not is_production(row):
        reasons.append("consistently low CPU vs request in snapshot")
        score = min(score, 0)

    if row.idle and is_production(row):
        reasons.append("low utilization but production context — review change window")
        score += 1

    if row.replicas >= 2 and row.cpu_ratio < 15 and not is_production(row):
        reasons.append("replicated deployment with low utilization")
        score = max(score - 1, 0)

    if not reasons:
        reasons.append("moderate signals — validate in staging before production")

    if score >= 3:
        return "HIGH", reasons
    if score >= 1:
        return "MEDIUM", reasons
    return "LOW", reasons


def assess_confidence(row: WorkloadRow) -> tuple[str, list[str]]:
    reasons = [
        "only snapshot metrics available (metrics-server)",
        "no historical Prometheus data connected",
    ]

    if row.cpu_usage == 0 and row.mem_usage == 0:
        reasons.append("no usage observed for running pods in this snapshot")
        return "LOW", reasons

    if row.replicas == 0:
        reasons.append("deployment scaled to zero replicas")
        return "LOW", reasons

    signals = 0
    if row.cpu_req > 0 and row.cpu_usage > 0:
        signals += 1
        reasons.append("CPU usage visible in current snapshot")
    if row.mem_req > 0 and row.mem_usage > 0:
        signals += 1
        reasons.append("memory usage visible in current snapshot")

    if row.cpu_ratio < 5 and row.cpu_req > 200:
        reasons.append("very low CPU utilization — use conservative review targets")

    if signals >= 2 and row.cpu_ratio < 40:
        return "MEDIUM", reasons
    if signals >= 1:
        return "MEDIUM", reasons
    return "LOW", reasons


def enrich_workload(row: WorkloadRow) -> None:
    row.annual_waste = annual_usd(row.monthly_waste)
    row.categories = classify_categories(row)
    row.risk_level, row.risk_reasons = assess_risk(row)
    row.confidence_level, row.confidence_reasons = assess_confidence(row)


def build_executive_summary(
    workload_rows: list[WorkloadRow],
    namespace_summary: dict[str, NamespaceSummary],
    cluster_monthly_waste: float,
) -> ExecutiveSummary:
    annual = annual_usd(cluster_monthly_waste)
    top_ns = ""
    top_ns_annual = 0.0
    if namespace_summary:
        top_ns, ns_data = max(namespace_summary.items(), key=lambda x: x[1].waste_usd)
        top_ns_annual = ns_data.annual_waste

    top_ref = "—"
    top_wl_annual = 0.0
    if workload_rows:
        top = max(workload_rows, key=lambda r: r.monthly_waste)
        top_ref = f"{top.namespace}/{top.name}"
        top_wl_annual = top.annual_waste

    owned = sum(1 for r in workload_rows if r.owner != "unknown")
    coverage = round((owned / len(workload_rows)) * 100, 1) if workload_rows else 0.0
    high_count = sum(1 for r in workload_rows if r.priority == "HIGH")

    return ExecutiveSummary(
        monthly_waste=round(cluster_monthly_waste, 2),
        annual_waste=annual,
        top_namespace=top_ns or "—",
        top_namespace_annual=top_ns_annual,
        top_workload_ref=top_ref,
        top_workload_annual=top_wl_annual,
        ownership_coverage_pct=coverage,
        high_priority_count=high_count,
        workload_count=len(workload_rows),
        trends_available=False,
        trend_notes=[
            "Historical trends require Prometheus — not connected in snapshot mode.",
        ],
    )


def recommended_action_order(workload_rows: list[WorkloadRow], limit: int = 5) -> list[WorkloadRow]:
    risk_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    conf_rank = {"MEDIUM": 0, "LOW": 1, "HIGH": -1}

    candidates = [r for r in workload_rows if r.monthly_waste > 0 and r.priority in ("HIGH", "MEDIUM")]
    candidates.sort(
        key=lambda r: (
            -r.annual_waste,
            risk_rank.get(r.risk_level, 1),
            conf_rank.get(r.confidence_level, 1),
        ),
    )
    return candidates[:limit]


def top_unowned_waste(workload_rows: list[WorkloadRow], limit: int = 5) -> list[WorkloadRow]:
    unowned = [r for r in workload_rows if r.owner == "unknown" and r.monthly_waste > 0]
    unowned.sort(key=lambda r: r.annual_waste, reverse=True)
    return unowned[:limit]


def category_counts(workload_rows: list[WorkloadRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in workload_rows:
        for cat in row.categories:
            counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
