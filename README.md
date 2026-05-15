# IdleKube

IdleKube is a lightweight Kubernetes CLI for spotting low-utilization workloads, overprovisioned CPU/memory requests, missing ownership labels, and possible resource waste.

It uses Kubernetes API data and live metrics-server usage to generate a fast operational snapshot.

It is **not** a billing tool, an auto-rightsizer, or a replacement for Prometheus, OpenCost, or Kubecost. Use it to decide **where to look first** — for audits, cleanup, learning, and prioritization.

## What it shows

- Potential monthly and annual waste (configurable cost model)
- Highest optimization opportunities (namespace and workload)
- Namespace-level waste summary
- Top workloads to review first
- Missing ownership labels
- Snapshot-based request/limit **review targets** (low confidence)
- JSON, CSV, and HTML exports

## Quick start

```bash
git clone <repo-url>
cd idlekube

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

kubectl top pods -A
python3 main.py scan
```

`python3 main.py` runs `scan` by default. Use `python3 main.py scan --help` for options.

## Example output

<img width="3511" height="887" alt="Executive summary and namespace waste" src="https://github.com/user-attachments/assets/91f6dca4-050f-4976-9754-4c39766e1609" />
<img width="3152" height="596" alt="Review targets and recommended order" src="https://github.com/user-attachments/assets/f364ff67-da4b-4e0d-bf61-768908811c67" />

## Common commands

```bash
python3 main.py scan
python3 main.py scan -n payments
python3 main.py scan --cpu-cost 30 --memory-cost 5
python3 main.py scan --format json
python3 main.py scan --format csv
python3 main.py scan --format html
python3 main.py scan --format json --stdout
```

Cluster scans skip system namespaces (`kube-system`, `kube-public`, etc.) unless you filter with `-n`.

## Demo workloads

The repository includes optional demo workloads for local testing:

```bash
kubectl apply -f manifests/workloads.yaml
python3 main.py scan
```

IdleKube does not require these workloads. It scans Deployments already present in your cluster.

## Requirements

- Python 3.10+
- `kubectl` and a working kubeconfig
- [metrics-server](https://github.com/kubernetes-sigs/metrics-server) in the cluster

## Reports

IdleKube can export reports as JSON, CSV, or HTML. Files are saved under:

```text
reports/report-<scope>-<YYYYMMDD-HHMMSS>.<ext>
```

Examples:

```text
reports/report-cluster-20260515-143022.json
reports/report-payments-20260515-143022.html
```

- **JSON** — best for automation (`jq`, CI, dashboards). Includes summary, namespaces, workloads, and review targets. See a generated file for the full schema.
- **CSV** — flat workload rows for spreadsheets
- **HTML** — offline-friendly report for sharing (no CDN; open in a browser)

The `reports/` directory is generated output and is gitignored.

`--stdout` prints JSON or CSV to the terminal while still saving under `reports/`. HTML is file-only.

## Safety / limitations

IdleKube uses **snapshot** metrics from metrics-server.

This means:

- Estimates are approximate, not invoices
- Review-target confidence is **low** without historical data
- CPU/memory behavior over time is not analyzed yet
- Do **not** apply suggested values directly to production
- Validate with **7–30 days** of historical usage before changing requests or limits

IdleKube provides **suggested review targets**, not production-ready rightsizing.

## Troubleshooting

### metrics-server unavailable (`503`)

Local clusters (Kind, Minikube) often need:

```bash
kubectl patch deployment metrics-server -n kube-system --type=json -p='[
  {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}
]'
kubectl rollout status deployment/metrics-server -n kube-system
kubectl top pods -A
```

Install if missing: [metrics-server releases](https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml). On Minikube: `minikube addons enable metrics-server`.

### Connection refused to `127.0.0.1`

Your kubeconfig points at a local API that is not running. Start the cluster (`minikube start`, etc.) and run `kubectl cluster-info`.

### `command not found: python`

Use `python3`, or activate the venv: `source .venv/bin/activate`.

### `Got unexpected extra argument (scan)`

Use the scan subcommand: `python3 main.py scan` (or bare `python3 main.py`).

## Test

```bash
python3 scripts/verify.py
python3 main.py scan
python3 main.py scan --format json
python3 main.py scan --format html
```

## Project layout

```text
idlekube/
  models.py
  k8s.py
  compute.py
  insights.py
  recommendations.py
  formatters/
main.py
manifests/
reports/
scripts/
```

## Roadmap

- Prometheus historical analysis
- p95 / p99 utilization
- Deployment correlation
- OpenCost integration
- Owner/team mapping file
- Better confidence scoring from historical data

## License

MIT
