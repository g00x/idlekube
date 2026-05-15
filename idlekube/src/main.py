# idlekube is an experimental Kubernetes efficiency scanner.
# It uses current metrics-server data, so recommendations should be validated
# against historical usage before changing production requests.

from collections import defaultdict

from kubernetes import client, config
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import typer

app = typer.Typer()
console = Console()

SYSTEM_NAMESPACES = [
    "kube-system",
    "kube-public",
    "kube-node-lease",
    "default",
]

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


def get_owner(labels: dict) -> str:
    if not labels:
        return "unknown"

    for key in ["owner", "team", "app.kubernetes.io/team", "app.kubernetes.io/owner"]:
        if key in labels:
            return labels[key]

    return "unknown"


def get_service(labels: dict, fallback_name: str) -> str:
    if not labels:
        return fallback_name

    for key in ["app", "service", "app.kubernetes.io/name"]:
        if key in labels:
            return labels[key]

    return fallback_name


def get_environment(labels: dict) -> str:
    if not labels:
        return "unknown"

    for key in ["env", "environment", "app.kubernetes.io/environment"]:
        if key in labels:
            return labels[key]

    return "unknown"


def get_pod_metrics():
    custom_api = client.CustomObjectsApi()

    try:
        metrics = custom_api.list_cluster_custom_object(
            group="metrics.k8s.io",
            version="v1beta1",
            plural="pods",
        )
    except Exception as e:
        console.print(f"[red]Could not read metrics-server data: {e}[/red]")
        return {}

    pod_usage = {}

    for item in metrics.get("items", []):
        namespace = item["metadata"]["namespace"]
        pod_name = item["metadata"]["name"]

        total_cpu_usage = 0
        total_memory_usage = 0

        for container in item.get("containers", []):
            usage = container.get("usage", {})
            total_cpu_usage += cpu_to_millicores(usage.get("cpu"))
            total_memory_usage += memory_to_mib(usage.get("memory"))

        pod_usage[(namespace, pod_name)] = {
            "cpu_m": total_cpu_usage,
            "memory_mib": total_memory_usage,
        }

    return pod_usage


@app.command()
def scan(
    cpu_cost: float = typer.Option(25.0, help="Monthly cost per CPU core"),
    memory_cost: float = typer.Option(4.0, help="Monthly cost per GB memory"),
):
    config.load_kube_config()

    apps_v1 = client.AppsV1Api()
    core_v1 = client.CoreV1Api()

    pod_metrics = get_pod_metrics()

    deployments = apps_v1.list_deployment_for_all_namespaces()
    pods = core_v1.list_pod_for_all_namespaces()

    pods_by_deployment = {}

    for pod in pods.items:
        namespace = pod.metadata.namespace
        pod_name = pod.metadata.name

        if namespace in SYSTEM_NAMESPACES:
            continue

        owner_name = None

        if pod.metadata.owner_references:
            for owner in pod.metadata.owner_references:
                if owner.kind == "ReplicaSet":
                    owner_name = owner.name

        if not owner_name:
            continue

        deployment_name = owner_name.rsplit("-", 1)[0]
        pods_by_deployment.setdefault((namespace, deployment_name), []).append(pod_name)

    workload_rows = []
    recommendations = []

    namespace_summary = defaultdict(
        lambda: {
            "cpu_req": 0,
            "cpu_usage": 0,
            "mem_req": 0,
            "mem_usage": 0,
            "waste_usd": 0.0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "workloads": 0,
            "owners": set(),
        }
    )

    cluster_cpu_req = 0
    cluster_cpu_usage = 0
    cluster_mem_req = 0
    cluster_mem_usage = 0
    cluster_waste_usd = 0.0

    for deploy in deployments.items:
        namespace = deploy.metadata.namespace

        if namespace in SYSTEM_NAMESPACES:
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

        for pod_name in pods_by_deployment.get((namespace, name), []):
            usage = pod_metrics.get((namespace, pod_name), {})
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

        if total_cpu_req > 0 and cpu_ratio < 10:
            problems.append("cpu overprovisioned")
        if total_mem_req > 0 and mem_ratio < 25:
            problems.append("memory overprovisioned")
        if idle:
            problems.append("low utilization workload")
        if owner == "unknown":
            problems.append("unknown owner")

        priority = get_priority(
            unused_cpu=unused_cpu,
            unused_mem=unused_mem,
            idle=idle,
            missing_limits=missing_limits,
            monthly_waste=monthly_waste,
        )

        workload_rows.append(
            {
                "namespace": namespace,
                "name": name,
                "service": service,
                "owner": owner,
                "environment": environment,
                "replicas": replicas,
                "cpu_req": total_cpu_req,
                "cpu_usage": total_cpu_usage,
                "unused_cpu": unused_cpu,
                "mem_req": total_mem_req,
                "mem_usage": total_mem_usage,
                "unused_mem": unused_mem,
                "cpu_ratio": cpu_ratio,
                "mem_ratio": mem_ratio,
                "monthly_waste": monthly_waste,
                "priority": priority,
                "problems": problems,
                "missing_limits": missing_limits,
                "idle": idle,
            }
        )

        ns = namespace_summary[namespace]
        ns["cpu_req"] += total_cpu_req
        ns["cpu_usage"] += total_cpu_usage
        ns["mem_req"] += total_mem_req
        ns["mem_usage"] += total_mem_usage
        ns["waste_usd"] += monthly_waste
        ns["workloads"] += 1
        ns["owners"].add(owner)
        ns[priority.lower()] += 1

        cluster_cpu_req += total_cpu_req
        cluster_cpu_usage += total_cpu_usage
        cluster_mem_req += total_mem_req
        cluster_mem_usage += total_mem_usage
        cluster_waste_usd += monthly_waste

    workload_rows.sort(
        key=lambda x: (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[x["priority"]],
            x["monthly_waste"],
            x["unused_cpu"],
            x["unused_mem"],
        ),
        reverse=True,
    )

    unused_cpu_total = max(cluster_cpu_req - cluster_cpu_usage, 0)
    unused_mem_total = max(cluster_mem_req - cluster_mem_usage, 0)

    cpu_efficiency = round((cluster_cpu_usage / cluster_cpu_req) * 100, 2) if cluster_cpu_req else 0
    memory_efficiency = round((cluster_mem_usage / cluster_mem_req) * 100, 2) if cluster_mem_req else 0

    summary = (
        f"[bold]Cluster Summary[/bold]\n\n"
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

    console.print(Panel(summary, title="idlekube"))

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
        key=lambda item: item[1]["waste_usd"],
        reverse=True,
    )

    for namespace, data in sorted_namespaces:
        ns_unused_cpu = max(data["cpu_req"] - data["cpu_usage"], 0)
        ns_unused_mem = max(data["mem_req"] - data["mem_usage"], 0)
        owners = ", ".join(sorted(data["owners"]))

        ns_table.add_row(
            namespace,
            str(data["workloads"]),
            owners,
            f"{data['cpu_req']}m",
            f"{ns_unused_cpu}m",
            f"{data['mem_req']}Mi",
            f"{ns_unused_mem}Mi",
            f"${round(data['waste_usd'], 2)}",
            str(data["high"]),
            str(data["medium"]),
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

    for row in workload_rows:
        workload_table.add_row(
            row["namespace"],
            row["name"],
            row["owner"],
            f"{row['cpu_req']}m",
            f"{row['cpu_usage']}m",
            f"{row['unused_cpu']}m",
            f"{row['mem_req']}Mi",
            f"{row['mem_usage']}Mi",
            f"{row['unused_mem']}Mi",
            f"${row['monthly_waste']}",
            colored_priority(row["priority"]),
            ", ".join(row["problems"]) if row["problems"] else "OK",
        )

        if row["priority"] in ["HIGH", "MEDIUM"]:
            recommendations.append(row)

    console.print(workload_table)

    console.print("\n[bold magenta]Top Optimization Targets[/bold magenta]\n")

    if recommendations:
        for row in recommendations[:10]:
            console.print(
                f"• [{ 'red' if row['priority'] == 'HIGH' else 'yellow' }]"
                f"{row['namespace']}/{row['name']}[/{ 'red' if row['priority'] == 'HIGH' else 'yellow' }]"
                f" — {row['priority']} priority, estimated optimization potential ${row['monthly_waste']}/mo. "
                f"Owner: {row['owner']}. "
                f"Potentially unused CPU: {row['unused_cpu']}m, potentially unused memory: {row['unused_mem']}Mi. "
                f"Reason: {', '.join(row['problems'])}."
            )
    else:
        console.print("[green]No recommendations[/green]")

    console.print("\n[bold cyan]Suggested Next Actions[/bold cyan]\n")

    high_targets = [row for row in workload_rows if row["priority"] == "HIGH"]
    unknown_owner_targets = [row for row in workload_rows if row["owner"] == "unknown"]

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


if __name__ == "__main__":
    app()