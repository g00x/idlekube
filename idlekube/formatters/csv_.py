import csv
import io


def write_csv(data: dict, output_path: str | None) -> None:
    fieldnames = [
        "namespace",
        "deployment",
        "service",
        "owner",
        "environment",
        "replicas",
        "cpu_requested_m",
        "cpu_used_m",
        "cpu_unused_m",
        "cpu_utilization_pct",
        "memory_requested_mib",
        "memory_used_mib",
        "memory_unused_mib",
        "memory_utilization_pct",
        "estimated_monthly_waste_usd",
        "estimated_annual_waste_usd",
        "priority",
        "categories",
        "risk_level",
        "confidence_level",
        "idle",
        "missing_limits",
        "problems",
        "suggested_cpu_request_m",
        "suggested_cpu_limit_m",
        "suggested_memory_request_mib",
        "suggested_memory_limit_mib",
    ]

    rows = []
    for w in data["workloads"]:
        row = dict(w)
        row["problems"] = ";".join(w["problems"])
        row["categories"] = ";".join(w.get("categories", []))
        row["idle"] = str(w["idle"]).lower()
        row["missing_limits"] = str(w["missing_limits"]).lower()
        rec = w.get("recommendation")
        if rec is None:
            row["suggested_cpu_request_m"] = ""
            row["suggested_cpu_limit_m"] = ""
            row["suggested_memory_request_mib"] = ""
            row["suggested_memory_limit_mib"] = ""
        else:
            row["suggested_cpu_request_m"] = rec["suggested_cpu_request_m"]
            row["suggested_cpu_limit_m"] = rec["suggested_cpu_limit_m"]
            row["suggested_memory_request_mib"] = rec["suggested_memory_request_mib"]
            row["suggested_memory_limit_mib"] = rec["suggested_memory_limit_mib"]
        rows.append(row)

    if output_path:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        print(buf.getvalue(), end="")
