# IdleKube

IdleKube is a small terminal-based Kubernetes efficiency scanner.

It helps surface:

* low-utilization workloads
* overprovisioned CPU and memory requests
* estimated resource waste
* namespace-level inefficiencies
* missing ownership labels
* optimization priorities

It is not a billing tool.

The goal is to help identify where to look first when reviewing Kubernetes resource usage and operational waste.

---

# Why I built this

I kept noticing the same pattern in Kubernetes clusters:

teams often overprovision workloads because nobody fully trusts actual workload behavior, while operational visibility and cost visibility are usually disconnected.

IdleKube is a small experiment to make those inefficiencies easier to spot.

---

# Screenshot

<img width="3511" height="887" alt="obraz" src="https://github.com/user-attachments/assets/91f6dca4-050f-4976-9754-4c39766e1609" />
<img width="3152" height="596" alt="obraz" src="https://github.com/user-attachments/assets/f364ff67-da4b-4e0d-bf61-768908811c67" />

Example output includes:

* cluster-level efficiency summary
* namespace-level optimization overview
* workload optimization priorities
* estimated monthly optimization potential
* suggested next actions

---

# Features

* Detect low-utilization workloads
* Detect overprovisioned CPU/memory requests
* Estimate potential monthly waste
* Surface missing ownership labels
* Prioritize optimization targets
* Generate actionable next steps
* Filter scans to a single namespace (team, environment, or service boundary)

---

# Requirements

* Python 3.10+
* Kubernetes cluster access
* kubeconfig configured locally
* metrics-server installed in the cluster

---

# Install

Create virtual environment:

```bash
python3 -m venv .venv
```

Activate environment:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Quick Start

Make sure metrics-server is installed and kubeconfig is configured locally.

Verify metrics are available:

```bash
kubectl top pods -A
```

Run IdleKube:

```bash
python main.py scan
```

---

# Demo workloads

The repository contains example Kubernetes workloads inside:

`manifests/workloads.yaml`

These are optional demo workloads used for local testing on environments like:

* Minikube
* Kind
* local Kubernetes clusters

You can deploy them with:

```bash
kubectl apply -f manifests/workloads.yaml
```

IdleKube itself does not depend on these workloads.

It scans whatever workloads already exist in your cluster using:

* Kubernetes API
* metrics-server metrics

---

# Usage

Run a full cluster scan (system namespaces such as `kube-system` are skipped by default):

```bash
python main.py scan
```

## Namespace filtering

To analyze only one namespace — useful when reviewing a single team, product, or environment:

```bash
python main.py scan --namespace payments
```

Short form:

```bash
python main.py scan -n payments
```

With a namespace filter, IdleKube:

* queries only Deployments and Pods in that namespace
* reads metrics-server data scoped to that namespace
* shows a namespace-focused summary panel (instead of a full-cluster summary)

If the namespace does not exist, IdleKube exits with an error. If it exists but has no Deployments, you get a clear message and no workload table.

You can still pass cost options together with a namespace filter:

```bash
python main.py scan -n backend --cpu-cost 30 --memory-cost 5
```

---

# Example use cases

IdleKube can be useful for:

* quick Kubernetes cluster reviews
* identifying obvious overprovisioning
* platform engineering audits
* FinOps reviews
* operational cleanup efforts
* improving workload ownership visibility
* reviewing one namespace at a time (e.g. `payments`, `backend`, `staging`)

---

# Important note

IdleKube currently uses snapshot metrics from metrics-server.

This means:

* recommendations are approximate
* workload behavior over time is not analyzed yet
* output should be used for prioritization, not direct production changes

Before modifying production requests/limits, validate workload behavior using longer historical windows (Prometheus, OpenCost, observability tooling, etc.).

---

# Possible future improvements

* Prometheus historical analysis
* p95 / p99 utilization analysis
* deployment correlation
* OpenCost integration
* JSON export
* owner/team mapping
* recommendation confidence scoring

---

# License

MIT
