from datetime import datetime, timezone
from typing import Optional

from idlekube.insights import annual_usd, build_executive_summary, enrich_workload
from idlekube.k8s import get_environment, get_owner, get_service, include_namespace
from idlekube.models import NamespaceSummary, WorkloadRow
from idlekube.recommendations import compute_recommendation


def cpu_to_millicores(cpu: str) -> int:
    if cpu is None:
        return 0
    if cpu.endswith("n"):
        return int(cpu.replace("n", "")) // 1_000_000
    if cpu.endswith("u"):
        return int(cpu.replace("u", "")) // 1000
    if cpu.endswith("m"):
        return int(cpu.replace("m", ""))
    return int(float(cpu) * 1000)


def memory_to_mib(memory: str) -> int:
    if memory is None:
        return 0

    memory = memory.lower()

    if memory.endswith("ki"):
        return int(float(memory.replace("ki", "")) / 1024)
    if memory.endswith("mi"):
        return int(memory.replace("mi", ""))
    if memory.endswith("gi"):
        return int(float(memory.replace("gi", "")) * 1024)

    return int(memory) // (1024 * 1024)


def estimate_monthly_waste(
    unused_cpu_m: int,
    unused_mem_mib: int,
    cpu_cost_per_core_month: float,
    memory_cost_per_gb_month: float,
) -> float:
    unused_cpu_cores = unused_cpu_m / 1000
    unused_mem_gb = unused_mem_mib / 1024

    cpu_cost = unused_cpu_cores * cpu_cost_per_core_month
    memory_cost = unused_mem_gb * memory_cost_per_gb_month

    return round(cpu_cost + memory_cost, 2)


def get_priority(
    unused_cpu: int,
    unused_mem: int,
    idle: bool,
    missing_limits: bool,
    monthly_waste: float,
) -> str:
    if monthly_waste >= 50 or unused_cpu > 1000 or unused_mem > 2048 or idle:
        return "HIGH"

    if monthly_waste >= 10 or unused_cpu > 300 or unused_mem > 512 or missing_limits:
        return "MEDIUM"

    return "LOW"


def colored_priority(priority: str) -> str:
    if priority == "HIGH":
        return "[red]HIGH[/red]"
    if priority == "MEDIUM":
        return "[yellow]MEDIUM[/yellow]"
    return "[green]LOW[/green]"


def run_scan(
    deployments,
    pods,
    pod_metrics: dict,
    namespace_filter: Optional[str],
    cpu_cost: float,
    memory_cost: float,
    cost: bool = False,
) -> tuple[list[WorkloadRow], dict[str, NamespaceSummary]]:
    pods_by_deployment = {}

    for pod in pods.items:
        ns = pod.metadata.namespace
        pod_name = pod.metadata.name

        if not include_namespace(ns, namespace_filter):
            continue

        owner_name = None

        if pod.metadata.owner_references:
            for owner in pod.metadata.owner_references:
                if owner.kind == "ReplicaSet":
                    owner_name = owner.name

        if not owner_name:
            continue

        deployment_name = owner_name.rsplit("-", 1)[0]
        pods_by_deployment.setdefault((ns, deployment_name), []).append(pod_name)

    workload_rows: list[WorkloadRow] = []
    namespace_summary: dict[str, NamespaceSummary] = {}

    for deploy in deployments.items:
        ns = deploy.metadata.namespace

        if not include_namespace(ns, namespace_filter):
            continue

        name = deploy.metadata.name
        replicas = deploy.spec.replicas or 0
        labels = deploy.metadata.labels or {}

        owner = get_owner(labels)
        service = get_service(labels, name)
        environment = get_environment(labels)

        total_cpu_req = 0
        total_mem_req = 0
        problems = []
        missing_limits = False

        for container in deploy.spec.template.spec.containers:
            resources = container.resources
            requests = resources.requests or {}
            limits = resources.limits or {}

            cpu_req = requests.get("cpu")
            mem_req = requests.get("memory")
            cpu_limit = limits.get("cpu")
            mem_limit = limits.get("memory")

            if not cpu_req:
                problems.append("missing cpu request")
            if not mem_req:
                problems.append("missing memory request")

            if not cpu_limit:
                missing_limits = True
                problems.append("missing cpu limit")
            if not mem_limit:
                missing_limits = True
                problems.append("missing memory limit")

            total_cpu_req += cpu_to_millicores(cpu_req) * replicas
            total_mem_req += memory_to_mib(mem_req) * replicas

        total_cpu_usage = 0
        total_mem_usage = 0

        for pod_name in pods_by_deployment.get((ns, name), []):
            usage = pod_metrics.get((ns, pod_name), {})
            total_cpu_usage += usage.get("cpu_m", 0)
            total_mem_usage += usage.get("memory_mib", 0)

        unused_cpu = max(total_cpu_req - total_cpu_usage, 0)
        unused_mem = max(total_mem_req - total_mem_usage, 0)

        cpu_ratio = round((total_cpu_usage / total_cpu_req) * 100, 2) if total_cpu_req else 0
        mem_ratio = round((total_mem_usage / total_mem_req) * 100, 2) if total_mem_req else 0

        idle = total_cpu_req > 500 and total_cpu_usage <= 5
        monthly_waste = estimate_monthly_waste(
            unused_cpu,
            unused_mem,
            cpu_cost,
            memory_cost,
        )

        priority = get_priority(
            unused_cpu=unused_cpu,
            unused_mem=unused_mem,
            idle=idle,
            missing_limits=missing_limits,
            monthly_waste=monthly_waste,
        )

        row = WorkloadRow(
            namespace=ns,
            name=name,
            service=service,
            owner=owner,
            environment=environment,
            replicas=replicas,
            cpu_req=total_cpu_req,
            cpu_usage=total_cpu_usage,
            unused_cpu=unused_cpu,
            mem_req=total_mem_req,
            mem_usage=total_mem_usage,
            unused_mem=unused_mem,
            cpu_ratio=cpu_ratio,
            mem_ratio=mem_ratio,
            monthly_waste=monthly_waste,
            priority=priority,
            problems=problems,
            missing_limits=missing_limits,
            idle=idle,
        )
        enrich_workload(row)
        row.recommendation = compute_recommendation(row)
        workload_rows.append(row)

        if ns not in namespace_summary:
            namespace_summary[ns] = NamespaceSummary(namespace=ns)
        ns_data = namespace_summary[ns]
        ns_data.cpu_req += total_cpu_req
        ns_data.cpu_usage += total_cpu_usage
        ns_data.mem_req += total_mem_req
        ns_data.mem_usage += total_mem_usage
        ns_data.waste_usd += monthly_waste
        ns_data.workloads += 1
        ns_data.owners.add(owner)
        if priority == "HIGH":
            ns_data.high += 1
        elif priority == "MEDIUM":
            ns_data.medium += 1
        else:
            ns_data.low += 1

    workload_rows.sort(
        key=lambda x: (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[x.priority],
            x.monthly_waste,
            x.unused_cpu,
            x.unused_mem,
        ),
        reverse=True,
    )

    return workload_rows, dict(namespace_summary)


def build_output_dict(
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
) -> dict:
    unused_cpu_total = max(cluster_cpu_req - cluster_cpu_usage, 0)
    unused_mem_total = max(cluster_mem_req - cluster_mem_usage, 0)
    cpu_efficiency = (
        round((cluster_cpu_usage / cluster_cpu_req) * 100, 2) if cluster_cpu_req else 0
    )
    memory_efficiency = (
        round((cluster_mem_usage / cluster_mem_req) * 100, 2) if cluster_mem_req else 0
    )

    namespaces = []
    sorted_namespaces = sorted(
        namespace_summary.items(),
        key=lambda item: item[1].waste_usd,
        reverse=True,
    )
    for namespace, data in sorted_namespaces:
        ns_unused_cpu = max(data.cpu_req - data.cpu_usage, 0)
        ns_unused_mem = max(data.mem_req - data.mem_usage, 0)
        namespaces.append(
            {
                "namespace": namespace,
                "workload_count": data.workloads,
                "owners": sorted(data.owners),
                "cpu_requested_m": data.cpu_req,
                "cpu_used_m": data.cpu_usage,
                "cpu_unused_m": ns_unused_cpu,
                "memory_requested_mib": data.mem_req,
                "memory_used_mib": data.mem_usage,
                "memory_unused_mib": ns_unused_mem,
                "estimated_monthly_waste_usd": round(data.waste_usd, 2),
                "estimated_annual_waste_usd": data.annual_waste,
                "high_priority_count": data.high,
                "medium_priority_count": data.medium,
                "low_priority_count": data.low,
            }
        )

    workloads = []
    for row in workload_rows:
        rec = row.recommendation
        recommendation = None
        if rec is not None:
            recommendation = {
                "suggested_cpu_request_m": rec.suggested_cpu_request_m,
                "suggested_cpu_limit_m": rec.suggested_cpu_limit_m,
                "suggested_memory_request_mib": rec.suggested_memory_request_mib,
                "suggested_memory_limit_mib": rec.suggested_memory_limit_mib,
                "confidence": rec.confidence,
                "confidence_reasons": rec.confidence_reasons,
                "observed_cpu_m": rec.observed_cpu_m,
                "observed_memory_mib": rec.observed_memory_mib,
                "note": rec.note,
            }
        workloads.append(
            {
                "namespace": row.namespace,
                "deployment": row.name,
                "service": row.service,
                "owner": row.owner,
                "environment": row.environment,
                "replicas": row.replicas,
                "cpu_requested_m": row.cpu_req,
                "cpu_used_m": row.cpu_usage,
                "cpu_unused_m": row.unused_cpu,
                "cpu_utilization_pct": row.cpu_ratio,
                "memory_requested_mib": row.mem_req,
                "memory_used_mib": row.mem_usage,
                "memory_unused_mib": row.unused_mem,
                "memory_utilization_pct": row.mem_ratio,
                "estimated_monthly_waste_usd": row.monthly_waste,
                "estimated_annual_waste_usd": row.annual_waste,
                "priority": row.priority,
                "categories": row.categories,
                "risk_level": row.risk_level,
                "risk_reasons": row.risk_reasons,
                "confidence_level": row.confidence_level,
                "confidence_reasons": row.confidence_reasons,
                "idle": row.idle,
                "missing_limits": row.missing_limits,
                "problems": row.problems,
                "recommendation": recommendation,
            }
        )

    executive = build_executive_summary(workload_rows, namespace_summary, cluster_waste_usd)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope": "namespace" if namespace_filter else "cluster",
            "namespace_filter": namespace_filter,
            "cost_model": {
                "cpu_per_core_month_usd": cpu_cost,
                "memory_per_gb_month_usd": memory_cost,
            },
        },
        "summary": {
            "cpu_requested_m": cluster_cpu_req,
            "cpu_used_m": cluster_cpu_usage,
            "cpu_unused_m": unused_cpu_total,
            "cpu_efficiency_pct": cpu_efficiency,
            "memory_requested_mib": cluster_mem_req,
            "memory_used_mib": cluster_mem_usage,
            "memory_unused_mib": unused_mem_total,
            "memory_efficiency_pct": memory_efficiency,
            "estimated_monthly_waste_usd": round(cluster_waste_usd, 2),
            "estimated_annual_waste_usd": annual_usd(cluster_waste_usd),
        },
        "executive_summary": {
            "potential_annual_savings_usd": executive.annual_waste,
            "potential_monthly_savings_usd": executive.monthly_waste,
            "highest_waste_namespace": executive.top_namespace,
            "highest_waste_namespace_annual_usd": executive.top_namespace_annual,
            "most_overprovisioned_workload": executive.top_workload_ref,
            "most_overprovisioned_workload_annual_usd": executive.top_workload_annual,
            "ownership_coverage_pct": executive.ownership_coverage_pct,
            "high_priority_targets": executive.high_priority_count,
            "trends_available": executive.trends_available,
            "trend_notes": executive.trend_notes,
        },
        "namespaces": namespaces,
        "workloads": workloads,
    }
