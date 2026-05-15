from typing import Optional

from idlekube.models import Recommendation, WorkloadRow

CPU_MULTIPLIER = 2.0
CPU_LIMIT_MULTIPLIER = 2.0
CPU_FLOOR_M = 10

MEMORY_MULTIPLIER = 1.5
MEMORY_LIMIT_MULTIPLIER = 1.5
MEMORY_FLOOR_MIB = 32

IMPROVEMENT_THRESHOLD = 0.20


def compute_recommendation(row: WorkloadRow) -> Optional[Recommendation]:
    """
    Returns a Recommendation if the workload is overprovisioned and we have
    enough data to suggest new values. Returns None if data is insufficient.
    """
    if row.cpu_usage == 0 and row.mem_usage == 0:
        return None

    if row.replicas == 0:
        return None

    if row.cpu_req == 0 and row.mem_req == 0:
        return None

    suggested_cpu_req = max(int(row.cpu_usage * CPU_MULTIPLIER), CPU_FLOOR_M)
    suggested_cpu_limit = int(suggested_cpu_req * CPU_LIMIT_MULTIPLIER)

    suggested_mem_req = max(int(row.mem_usage * MEMORY_MULTIPLIER), MEMORY_FLOOR_MIB)
    suggested_mem_limit = int(suggested_mem_req * MEMORY_LIMIT_MULTIPLIER)

    cpu_improvement = (row.cpu_req - suggested_cpu_req) / row.cpu_req if row.cpu_req else 0
    mem_improvement = (row.mem_req - suggested_mem_req) / row.mem_req if row.mem_req else 0

    if cpu_improvement < IMPROVEMENT_THRESHOLD and mem_improvement < IMPROVEMENT_THRESHOLD:
        return None

    return Recommendation(
        suggested_cpu_request_m=suggested_cpu_req,
        suggested_cpu_limit_m=suggested_cpu_limit,
        suggested_memory_request_mib=suggested_mem_req,
        suggested_memory_limit_mib=suggested_mem_limit,
        confidence="low",
        note="Snapshot estimate. Validate against historical usage before applying to production.",
    )
