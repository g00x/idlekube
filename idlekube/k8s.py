from typing import Optional

from kubernetes import client
from kubernetes.client.rest import ApiException

from idlekube.console import console

SYSTEM_NAMESPACES = [
    "kube-system",
    "kube-public",
    "kube-node-lease",
    "default",
]


def include_namespace(namespace: str, namespace_filter: Optional[str]) -> bool:
    if namespace_filter is not None:
        return namespace == namespace_filter
    return namespace not in SYSTEM_NAMESPACES


def print_metrics_server_local_fix() -> None:
    console.print(
        "\n[yellow]Common fix for local/dev clusters (Kind, Minikube):[/yellow]\n"
        "  kubectl patch deployment metrics-server -n kube-system --type=json -p='[\n"
        '    {"op": "add", "path": "/spec/template/spec/containers/0/args/-", '
        '"value": "--kubelet-insecure-tls"}\n'
        "  ]'\n"
        "  kubectl rollout status deployment/metrics-server -n kube-system\n"
        "  kubectl top pods -A\n"
    )


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


def get_pod_metrics(namespace_filter: Optional[str] = None):
    from idlekube.compute import cpu_to_millicores, memory_to_mib

    custom_api = client.CustomObjectsApi()

    try:
        if namespace_filter is not None:
            metrics = custom_api.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace_filter,
                plural="pods",
            )
        else:
            metrics = custom_api.list_cluster_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                plural="pods",
            )
    except ApiException as e:
        console.print(f"[red]Could not read metrics-server data: {e}[/red]")
        if e.status == 503:
            print_metrics_server_local_fix()
        return {}
    except Exception as e:
        console.print(f"[red]Could not read metrics-server data: {e}[/red]")
        if "503" in str(e) or "Service Unavailable" in str(e):
            print_metrics_server_local_fix()
        return {}

    pod_usage = {}

    for item in metrics.get("items", []):
        namespace = item["metadata"]["namespace"]
        pod_name = item["metadata"]["name"]

        if not include_namespace(namespace, namespace_filter):
            continue

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
