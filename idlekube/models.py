from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Recommendation:
    suggested_cpu_request_m: int
    suggested_cpu_limit_m: int
    suggested_memory_request_mib: int
    suggested_memory_limit_mib: int
    confidence: str
    confidence_reasons: list[str]
    note: str
    observed_cpu_m: int = 0
    observed_memory_mib: int = 0


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
    annual_waste: float = 0.0
    categories: list[str] = field(default_factory=list)
    risk_level: str = "MEDIUM"
    risk_reasons: list[str] = field(default_factory=list)
    confidence_level: str = "LOW"
    confidence_reasons: list[str] = field(default_factory=list)


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

    @property
    def annual_waste(self) -> float:
        return round(self.waste_usd * 12, 2)


@dataclass
class ExecutiveSummary:
    monthly_waste: float
    annual_waste: float
    top_namespace: str
    top_namespace_annual: float
    top_workload_ref: str
    top_workload_annual: float
    ownership_coverage_pct: float
    high_priority_count: int
    workload_count: int
    trends_available: bool = False
    trend_notes: list[str] = field(default_factory=list)
