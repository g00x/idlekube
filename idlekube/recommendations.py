from typing import Optional

from idlekube.models import Recommendation, WorkloadRow

CPU_MULTIPLIER = 2.0
CPU_LIMIT_MULTIPLIER = 2.0
MEMORY_MULTIPLIER = 1.5
MEMORY_LIMIT_MULTIPLIER = 1.5

IMPROVEMENT_THRESHOLD = 0.20

CPU_REQUEST_MIN_M = 50
CPU_REQUEST_PREFERRED_M = 100
CPU_LIMIT_MIN_M = 100
CPU_LIMIT_PREFERRED_M = 200
MEMORY_REQUEST_MIN_MIB = 64
MEMORY_LIMIT_MIN_MIB = 128

NEAR_ZERO_CPU_M = 10

SNAPSHOT_CONFIDENCE = "LOW"
CONFIDENCE_REASONS = [
    "metrics-server snapshot only",
    "no historical Prometheus utilization available",
]

VALIDATION_NOTE = (
    "Validate against 7–30d utilization before modifying production requests or limits."
)


def _round_cpu_m(value: int) -> int:
    return max(10, int(round(value / 10) * 10))


def _round_mem_mib(value: int) -> int:
    return max(1, int(round(value)))


def _cpu_request_floor(observed_m: int) -> int:
    if observed_m <= NEAR_ZERO_CPU_M:
        return CPU_REQUEST_PREFERRED_M
    return CPU_REQUEST_MIN_M


def _cpu_limit_floor(observed_m: int) -> int:
    if observed_m <= NEAR_ZERO_CPU_M:
        return CPU_LIMIT_PREFERRED_M
    return CPU_LIMIT_MIN_M


def _suggest_cpu_request(observed_m: int) -> int:
    scaled = max(int(observed_m * CPU_MULTIPLIER), observed_m)
    floored = max(scaled, _cpu_request_floor(observed_m))
    return _round_cpu_m(floored)


def _suggest_cpu_limit(request_m: int, observed_m: int) -> int:
    scaled = max(int(request_m * CPU_LIMIT_MULTIPLIER), request_m)
    floored = max(scaled, _cpu_limit_floor(observed_m))
    return _round_cpu_m(floored)


def _suggest_memory_request(observed_mib: int) -> int:
    scaled = max(int(observed_mib * MEMORY_MULTIPLIER), observed_mib)
    floored = max(scaled, MEMORY_REQUEST_MIN_MIB)
    return _round_mem_mib(floored)


def _suggest_memory_limit(request_mib: int) -> int:
    scaled = max(int(request_mib * MEMORY_LIMIT_MULTIPLIER), request_mib)
    floored = max(scaled, MEMORY_LIMIT_MIN_MIB)
    return _round_mem_mib(floored)


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

    suggested_cpu_req = _suggest_cpu_request(row.cpu_usage) if row.cpu_req else 0
    suggested_cpu_limit = (
        _suggest_cpu_limit(suggested_cpu_req, row.cpu_usage) if suggested_cpu_req else 0
    )

    suggested_mem_req = _suggest_memory_request(row.mem_usage) if row.mem_req else 0
    suggested_mem_limit = (
        _suggest_memory_limit(suggested_mem_req) if suggested_mem_req else 0
    )

    cpu_improvement = (row.cpu_req - suggested_cpu_req) / row.cpu_req if row.cpu_req else 0
    mem_improvement = (row.mem_req - suggested_mem_req) / row.mem_req if row.mem_req else 0

    if cpu_improvement < IMPROVEMENT_THRESHOLD and mem_improvement < IMPROVEMENT_THRESHOLD:
        return None

    return Recommendation(
        suggested_cpu_request_m=suggested_cpu_req,
        suggested_cpu_limit_m=suggested_cpu_limit,
        suggested_memory_request_mib=suggested_mem_req,
        suggested_memory_limit_mib=suggested_mem_limit,
        confidence=SNAPSHOT_CONFIDENCE,
        confidence_reasons=list(CONFIDENCE_REASONS),
        note=VALIDATION_NOTE,
        observed_cpu_m=row.cpu_usage,
        observed_memory_mib=row.mem_usage,
    )
