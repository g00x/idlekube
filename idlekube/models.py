from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Recommendation:
    suggested_cpu_request_m: int
    suggested_cpu_limit_m: int
    suggested_memory_request_mib: int
    suggested_memory_limit_mib: int
    confidence: str
    note: str


@dataclass
class WorkloadRow:
    namespace: str
    name: str
    service: str
    owner: str
    environment: str
    replicas: int
    cpu_req: int
    cpu_usage: int
    unused_cpu: int
    mem_req: int
    mem_usage: int
    unused_mem: int
    cpu_ratio: float
    mem_ratio: float
    monthly_waste: float
    priority: str
    problems: list[str]
    missing_limits: bool
    idle: bool
    recommendation: Recommendation | None = None


@dataclass
class NamespaceSummary:
    namespace: str
    cpu_req: int = 0
    cpu_usage: int = 0
    mem_req: int = 0
    mem_usage: int = 0
    waste_usd: float = 0.0
    high: int = 0
    medium: int = 0
    low: int = 0
    workloads: int = 0
    owners: set = field(default_factory=set)
