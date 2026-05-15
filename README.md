# IdleKube

IdleKube is a small terminal-based Kubernetes efficiency scanner.

It helps surface:

* low-utilization workloads
* overprovisioned CPU and memory requests
* estimated optimization potential
* namespace-level inefficiencies
* missing ownership labels
* optimization priorities

It is not a billing tool.

The goal is to help identify where to look first when reviewing Kubernetes resource usage and operational waste.

---

# Why I built this

During Kubernetes and observability work, I kept seeing the same issue:

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

# Usage

Run the scanner:

```bash
python main.py
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
