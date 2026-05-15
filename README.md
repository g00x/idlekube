# IdleKube

IdleKube is a terminal-based Kubernetes efficiency scanner. It compares workload **requests** against live **usage** from metrics-server and highlights where CPU and memory look overprovisioned.

It is **not** a billing tool. Use it to decide **where to look first** before changing production requests or limits.

## Features

- Detect low-utilization workloads
- Detect overprovisioned CPU and memory requests
- Estimate potential monthly waste (configurable cost model)
- Surface missing ownership labels
- Prioritize optimization targets (HIGH / MEDIUM / LOW)
- Filter scans to a single namespace
- Export results as **JSON**, **CSV**, or **HTML** (saved under `reports/`)

## Requirements

- Python 3.10+
- `kubectl` and a working kubeconfig
- [metrics-server](https://github.com/kubernetes-sigs/metrics-server) in the cluster

## Install

```bash
git clone <your-repo-url>
cd idlekube

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick start

**1. Check cluster access**

```bash
kubectl cluster-info
kubectl get nodes
```

**2. Check metrics-server**

```bash
kubectl top pods -A
```

If this fails with `503` or `Service Unavailable`, see [Troubleshooting](#troubleshooting) below.

**3. (Optional) Deploy demo workloads**

```bash
kubectl apply -f manifests/workloads.yaml
```

**4. Run a scan**

```bash
python3 main.py scan
```

## Usage

IdleKube uses subcommands. The main command is **`scan`**.

```bash
python3 main.py --help
python3 main.py scan --help
```

### Table output (default)

Full cluster scan (skips system namespaces like `kube-system` by default):

```bash
python3 main.py scan
```

### Namespace filter

Scan one namespace only:

```bash
python3 main.py scan --namespace payments
python3 main.py scan -n payments
```

### Custom cost model

```bash
python3 main.py scan --cpu-cost 30 --memory-cost 5
python3 main.py scan -n backend --cpu-cost 30 --memory-cost 5
```

---

## JSON and CSV export

Whenever you use `--format json` or `--format csv`, IdleKube **always saves** a report next to `main.py`:

```text
reports/report-<scope>-<YYYYMMDD-HHMMSS>.json
```

| Scan | Example file |
|------|----------------|
| Full cluster | `reports/report-cluster-20260515-143022.json` |
| Namespace `payments` | `reports/report-payments-20260515-143022.json` |

The timestamp is **UTC** (same as `meta.generated_at` inside the JSON).

### Save JSON (most common)

```bash
python3 main.py scan --format json
python3 main.py scan -n payments --format json
```

You will see on stderr:

```text
Report saved: /home/you/idlekube/reports/report-payments-20260515-143022.json
```

Open the file:

```bash
ls reports/
cat reports/report-payments-*.json
```

### Pipe JSON to jq (`--stdout`)

By default, JSON goes **only** to the file (not stdout). To also print JSON for piping:

```bash
python3 main.py scan --format json --stdout | jq '.workloads[] | select(.priority == "HIGH")'
python3 main.py scan -n payments --format json --stdout | jq '.summary.estimated_monthly_waste_usd'
```

### CSV export

```bash
python3 main.py scan --format csv
python3 main.py scan -n payments --format csv --stdout
```

CSV contains **workloads only** (flat rows). Use JSON if you need cluster summary and per-namespace aggregation.

### JSON structure (overview)

```json
{
  "meta": {
    "generated_at": "2026-05-15T14:30:22Z",
    "scope": "namespace",
    "namespace_filter": "payments",
    "cost_model": { "cpu_per_core_month_usd": 25.0, "memory_per_gb_month_usd": 4.0 }
  },
  "summary": { "...": "cluster or namespace totals" },
  "namespaces": [ "... per-namespace rollup ..." ],
  "workloads": [ "... one object per Deployment ..." ]
}
```

All numeric fields are plain numbers (no `1200m` or `$` suffixes).

---

## HTML report

Offline-friendly report (no CDN, no Google Fonts). Opens in any browser; suitable for email attachments.

```bash
python3 main.py scan --format html
python3 main.py scan -n payments --format html
```

Saved as:

```text
reports/report-<scope>-<YYYYMMDD-HHMMSS>.html
```

Open it:

```bash
xdg-open reports/report-cluster-*.html    # Linux
open reports/report-cluster-*.html      # macOS
```

Features:

- Summary cards (CPU/memory efficiency, estimated waste)
- Sortable namespace and workload tables (click column headers; numeric sort is type-aware)
- Works fully offline

**Note:** `--stdout` is not supported for HTML (file only). Using `--stdout` with `--format html` exits with an error.

---

## Demo workloads

Optional manifests for local testing (Minikube, Kind, etc.):

```bash
kubectl apply -f manifests/workloads.yaml
python3 main.py scan
```

IdleKube does not require these workloads — it scans whatever Deployments already exist in your cluster.

## Screenshot

<img width="3511" height="887" alt="Cluster summary and namespace table" src="https://github.com/user-attachments/assets/91f6dca4-050f-4976-9754-4c39766e1609" />
<img width="3152" height="596" alt="Workload priorities and recommendations" src="https://github.com/user-attachments/assets/f364ff67-da4b-4e0d-bf61-768908811c67" />

## Troubleshooting

### `Connection refused` to `127.0.0.1`

Your kubeconfig points at a local API (Minikube/Kind) that is not running. Start the cluster and verify:

```bash
minikube start          # if using Minikube
kubectl cluster-info
```

### metrics-server returns `503`

On Kind, Minikube, and other local clusters, metrics-server often needs `--kubelet-insecure-tls`:

```bash
kubectl patch deployment metrics-server -n kube-system --type=json -p='[
  {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}
]'
kubectl rollout status deployment/metrics-server -n kube-system
kubectl top pods -A
```

Install metrics-server if missing:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Minikube:

```bash
minikube addons enable metrics-server
```

### `Got unexpected extra argument (scan)`

Use the `scan` subcommand explicitly:

```bash
python3 main.py scan
```

### `command not found: python`

Use `python3`, or activate the virtualenv:

```bash
source .venv/bin/activate
python main.py scan
```

### Old `report.json` in the project root

If you previously ran `python3 main.py scan --format json --output report.json`, that created a file in the repo root. That syntax is no longer used. Delete it:

```bash
rm -f report.json
```

Reports are always written under `reports/` with a timestamped name.

---

## How to test

**Repair `main.py` if you see errors** (duplicate code at the bottom of the file):

```bash
cd ~/idlekube
python3 fix_main.py
```

**Cluster + metrics**

```bash
kubectl top pods -A
kubectl apply -f manifests/workloads.yaml   # optional demo
```

**Commands**

```bash
python3 main.py scan                          # table in terminal
python3 main.py scan --format json            # -> reports/report-*.json
python3 main.py scan --format html            # -> reports/report-*.html
python3 main.py scan -n payments --format html
python3 main.py scan --format json --stdout | jq '.summary'
```

**HTML:** open `reports/report-*.html` in a browser (works offline). Click column headers to sort.

**Checklist**

- [ ] `scan` (table) unchanged
- [ ] JSON/CSV/HTML files appear in `reports/` with timestamp in the name
- [ ] HTML has no external URLs (offline OK)
- [ ] Table sort: `1000` before `200` on numeric columns
- [ ] `--format html --stdout` → error (no HTML on stdout)

---

## Important note

IdleKube uses **snapshot** metrics from metrics-server:

- Recommendations are approximate
- No historical p95/p99 analysis yet
- Use output for **prioritization**, not direct production changes

Before lowering requests or limits in production, validate behavior over a longer window (Prometheus, OpenCost, etc.).

## Roadmap

- Prometheus historical analysis
- p95 / p99 utilization
- Deployment correlation
- OpenCost integration
- Owner/team mapping file
- Recommendation confidence scoring

## License

MIT
