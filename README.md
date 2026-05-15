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
- Export results as **JSON** or **CSV** (stdout or timestamped files in `reports/`)

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

### Print JSON to the terminal (stdout)

Use this when you want to pipe output into `jq`, another script, or CI:

```bash
python3 main.py scan --format json
python3 main.py scan -n payments --format json
```

Example — list only HIGH priority workloads:

```bash
python3 main.py scan --format json | jq '.workloads[] | select(.priority == "HIGH")'
```

Example — read estimated monthly waste:

```bash
python3 main.py scan --format json | jq '.summary.estimated_monthly_waste_usd'
```

### Save JSON to `reports/` (with date and time in the filename)

Use the **`-o` / `--output` flag** (no filename needed). IdleKube creates the `reports/` directory and writes a timestamped file:

```bash
python3 main.py scan --format json -o
python3 main.py scan -n payments --format json --output
```

**Filename pattern:**

```text
reports/report-<scope>-<YYYYMMDD-HHMMSS>.json
```

| Command | Example file |
|---------|----------------|
| Full cluster | `reports/report-cluster-20260515-143022.json` |
| Namespace `payments` | `reports/report-payments-20260515-143022.json` |

The timestamp is **UTC** (`meta.generated_at` in the JSON uses the same format).

After saving, IdleKube prints a short message on stderr, for example:

```text
Report saved: reports/report-payments-20260515-143022.json
```

Open the latest report:

```bash
ls -t reports/*.json | head -1 | xargs cat
# or
cat reports/report-payments-*.json
```

### CSV export

Print to stdout:

```bash
python3 main.py scan --format csv
```

Save to `reports/`:

```bash
python3 main.py scan --format csv -o
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

### Stray files in the project root

Do **not** pass a filename to `--output`. Use the flag alone:

```bash
# correct
python3 main.py scan --format json -o

# wrong — can create odd files like "can" in the repo root
python3 main.py scan --output report.json
```

Reports belong in `reports/` only.

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
