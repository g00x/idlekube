"""Self-contained HTML report generator (no CDN, no external fonts)."""

import html
from typing import Any

_TAG = "di" + "v"


def _h(value: Any) -> str:
    return html.escape(str(value))


def _sort_cell(display: str, sort_value: Any) -> str:
    return f'<td data-sort-value="{_h(sort_value)}">{display}</td>'


def _card(label: str, value: str, extra_class: str = "") -> str:
    cls = f"card {extra_class}".strip()
    return (
        f"<{_TAG} class=\"{cls}\">"
        f"<{_TAG} class=\"label\">{_h(label)}</{_TAG}>"
        f"<{_TAG} class=\"value\">{value}</{_TAG}>"
        f"</{_TAG}>"
    )


def _suggested_cell(workload: dict) -> str:
    rec = workload.get("recommendation")
    note = "Snapshot estimate. Validate against historical usage before applying."
    if rec is None:
        return f'<td class="suggested muted" title="{_h(note)}">—</td>'
    cpu = f"cpu  →  {rec['suggested_cpu_request_m']}m / {rec['suggested_cpu_limit_m']}m"
    mem = (
        f"mem  →  {rec['suggested_memory_request_mib']}Mi / "
        f"{rec['suggested_memory_limit_mib']}Mi"
    )
    body = f"<span class=\"suggested-line\">{_h(cpu)}</span><br>"
    body += f"<span class=\"suggested-line\">{_h(mem)}</span>"
    return f'<td class="suggested" title="{_h(note)}">{body}</td>'


HTML_STYLES = """
:root {
  --color-bg: #0f1419;
  --color-surface: #1a2332;
  --color-surface-alt: #243044;
  --color-text: #e6edf3;
  --color-muted: #8b9cb3;
  --color-border: #2d3a4f;
  --color-accent: #3b82f6;
  --blue: #58a6ff;
  --color-high: #ef4444;
  --color-medium: #f59e0b;
  --color-low: #22c55e;
  --font-family: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif;
  --radius: 8px;
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem;
  font-family: var(--font-family);
  background: var(--color-bg);
  color: var(--color-text);
  line-height: 1.5;
}
h1, h2 { margin: 0 0 0.5rem; }
h1 { font-size: 1.75rem; }
h2 {
  font-size: 1.25rem;
  margin-top: 2rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}
.meta { color: var(--color-muted); font-size: 0.9rem; margin-bottom: 1.5rem; }
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}
.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: 1rem;
  box-shadow: var(--shadow);
}
.card .label {
  color: var(--color-muted);
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.card .value { font-size: 1.35rem; font-weight: 600; margin-top: 0.25rem; }
.card.waste .value { color: var(--color-high); }
.table-wrap { overflow-x: auto; margin-bottom: 1rem; }
table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-surface);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}
th, td {
  padding: 0.65rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
th {
  background: var(--color-surface-alt);
  color: var(--color-muted);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  cursor: pointer;
  user-select: none;
}
th:hover { color: var(--color-text); }
th.sort-asc::after { content: " \\25b2"; color: var(--color-accent); }
th.sort-desc::after { content: " \\25bc"; color: var(--color-accent); }
tr:hover td { background: var(--color-surface-alt); }
td.wrap { white-space: normal; max-width: 280px; }
td.suggested {
  white-space: normal;
  font-family: ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, monospace;
  font-size: 0.8rem;
  color: var(--blue);
}
td.suggested.muted { color: var(--color-muted); }
.suggested-line { display: block; }
.priority {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.priority-high { background: rgba(239, 68, 68, 0.2); color: var(--color-high); }
.priority-medium { background: rgba(245, 158, 11, 0.2); color: var(--color-medium); }
.priority-low { background: rgba(34, 197, 94, 0.2); color: var(--color-low); }
footer {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border);
  color: var(--color-muted);
  font-size: 0.85rem;
}
"""

HTML_SORT_SCRIPT = """
function parseSortValue(raw, sortType) {
  if (sortType === "number") {
    const stripped = String(raw).replace(/[^0-9.-]/g, "");
    const n = parseFloat(stripped);
    return Number.isNaN(n) ? 0 : n;
  }
  return String(raw).toLowerCase();
}

function sortTable(table, colIndex, sortType, ascending) {
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.querySelectorAll("tr"));
  rows.sort((a, b) => {
    const aCell = a.cells[colIndex];
    const bCell = b.cells[colIndex];
    const aVal = parseSortValue(
      aCell.getAttribute("data-sort-value") ?? aCell.textContent,
      sortType
    );
    const bVal = parseSortValue(
      bCell.getAttribute("data-sort-value") ?? bCell.textContent,
      sortType
    );
    if (aVal < bVal) return ascending ? -1 : 1;
    if (aVal > bVal) return ascending ? 1 : -1;
    return 0;
  });
  rows.forEach((row) => tbody.appendChild(row));
}

document.querySelectorAll("table.sortable").forEach((table) => {
  const headers = table.querySelectorAll("th");
  headers.forEach((th, index) => {
    const sortType = th.getAttribute("data-sort-type") || "string";
    th.addEventListener("click", () => {
      const ascending = !th.classList.contains("sort-asc");
      headers.forEach((h) => h.classList.remove("sort-asc", "sort-desc"));
      th.classList.add(ascending ? "sort-asc" : "sort-desc");
      sortTable(table, index, sortType, ascending);
    });
  });
});
"""


def write_html(data: dict, output_path: str) -> None:
    meta = data["meta"]
    summary = data["summary"]
    cost = meta["cost_model"]
    scope_label = (
        f"Namespace: {meta['namespace_filter']}"
        if meta["scope"] == "namespace"
        else "Cluster-wide"
    )

    cards = "".join(
        [
            _card("CPU efficiency", f"{summary['cpu_efficiency_pct']}%"),
            _card("Memory efficiency", f"{summary['memory_efficiency_pct']}%"),
            _card(
                "Monthly waste (est.)",
                f"${summary['estimated_monthly_waste_usd']}",
                "waste",
            ),
            _card(
                "Annual waste (est.)",
                f"${summary['estimated_annual_waste_usd']}",
                "waste",
            ),
            _card("CPU requested", f"{summary['cpu_requested_m']}m"),
            _card("CPU used", f"{summary['cpu_used_m']}m"),
        ]
    )

    ns_rows = []
    for ns in data["namespaces"]:
        ns_rows.append(
            "<tr>"
            + _sort_cell(_h(ns["namespace"]), ns["namespace"])
            + _sort_cell(str(ns["workload_count"]), ns["workload_count"])
            + f'<td class="wrap">{_h(", ".join(ns["owners"]))}</td>'
            + _sort_cell(f"{ns['cpu_requested_m']}m", ns["cpu_requested_m"])
            + _sort_cell(f"{ns['cpu_unused_m']}m", ns["cpu_unused_m"])
            + _sort_cell(f"{ns['memory_requested_mib']} Mi", ns["memory_requested_mib"])
            + _sort_cell(f"{ns['memory_unused_mib']} Mi", ns["memory_unused_mib"])
            + _sort_cell(f"${ns['estimated_monthly_waste_usd']}", ns["estimated_monthly_waste_usd"])
            + _sort_cell(str(ns["high_priority_count"]), ns["high_priority_count"])
            + _sort_cell(str(ns["medium_priority_count"]), ns["medium_priority_count"])
            + "</tr>"
        )

    workload_rows = []
    for w in data["workloads"]:
        priority = w["priority"].lower()
        problems = ", ".join(w["problems"]) if w["problems"] else "OK"
        workload_rows.append(
            "<tr>"
            + _sort_cell(_h(w["namespace"]), w["namespace"])
            + _sort_cell(_h(w["deployment"]), w["deployment"])
            + _sort_cell(_h(w["owner"]), w["owner"])
            + f'<td data-sort-value="{_h(w["priority"])}">'
            f'<span class="priority priority-{priority}">{_h(w["priority"])}</span></td>'
            + _sort_cell(f"${w['estimated_monthly_waste_usd']}", w["estimated_monthly_waste_usd"])
            + _sort_cell(f"{w['cpu_requested_m']}m", w["cpu_requested_m"])
            + _sort_cell(f"{w['cpu_used_m']}m", w["cpu_used_m"])
            + _sort_cell(f"{w['cpu_utilization_pct']}%", w["cpu_utilization_pct"])
            + _sort_cell(f"{w['memory_requested_mib']} Mi", w["memory_requested_mib"])
            + _sort_cell(f"{w['memory_used_mib']} Mi", w["memory_used_mib"])
            + _sort_cell(f"{w['memory_utilization_pct']}%", w["memory_utilization_pct"])
            + f'<td class="wrap">{_h(problems)}</td>'
            + _suggested_cell(w)
            + "</tr>"
        )

    ns_body = "".join(ns_rows) if ns_rows else '<tr><td colspan="10">No namespaces</td></tr>'
    wl_body = "".join(workload_rows) if workload_rows else '<tr><td colspan="13">No workloads</td></tr>'

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IdleKube Report — {_h(meta["generated_at"])}</title>
  <style>{HTML_STYLES}</style>
</head>
<body>
  <h1>IdleKube Report</h1>
  <p class="meta">
    {_h(scope_label)} · Generated {_h(meta["generated_at"])} UTC<br>
    Cost model: ${_h(cost["cpu_per_core_month_usd"])}/CPU core/mo,
    ${_h(cost["memory_per_gb_month_usd"])}/GB memory/mo
  </p>
  <{_TAG} class="cards">{cards}</{_TAG}>
  <h2>Namespace summary</h2>
  <{_TAG} class="table-wrap">
    <table class="sortable">
      <thead><tr>
        <th data-sort-type="string">Namespace</th>
        <th data-sort-type="number">Workloads</th>
        <th data-sort-type="string">Owners</th>
        <th data-sort-type="number">CPU req</th>
        <th data-sort-type="number">Unused CPU</th>
        <th data-sort-type="number">Mem req</th>
        <th data-sort-type="number">Unused mem</th>
        <th data-sort-type="number">Est. waste/mo</th>
        <th data-sort-type="number">High</th>
        <th data-sort-type="number">Medium</th>
      </tr></thead>
      <tbody>{ns_body}</tbody>
    </table>
  </{_TAG}>
  <h2>Workload priorities</h2>
  <{_TAG} class="table-wrap">
    <table class="sortable">
      <thead><tr>
        <th data-sort-type="string">Namespace</th>
        <th data-sort-type="string">Deployment</th>
        <th data-sort-type="string">Owner</th>
        <th data-sort-type="string">Priority</th>
        <th data-sort-type="number">Est. waste/mo</th>
        <th data-sort-type="number">CPU req</th>
        <th data-sort-type="number">CPU used</th>
        <th data-sort-type="number">CPU %</th>
        <th data-sort-type="number">Mem req</th>
        <th data-sort-type="number">Mem used</th>
        <th data-sort-type="number">Mem %</th>
        <th data-sort-type="string">Problems</th>
        <th data-sort-type="string">Suggested</th>
      </tr></thead>
      <tbody>{wl_body}</tbody>
    </table>
  </{_TAG}>
  <footer>
    Snapshot estimate from metrics-server. Use for prioritization only — validate with
    historical metrics before changing production requests.
  </footer>
  <script>{HTML_SORT_SCRIPT}</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(document)
