# idlekube

idlekube is a small terminal-based Kubernetes efficiency scanner.

It helps surface:

- low utilization workloads
- overprovisioned CPU and memory requests
- estimated monthly optimization potential
- namespace-level inefficiencies
- missing ownership labels
- optimization priorities

It is not a billing tool.
It is meant to help prioritize where to look first.

## Why I built this

During Kubernetes and observability work, I kept seeing the same issue:

teams often overprovision workloads because nobody fully trusts actual workload behavior, and cost visibility is usually disconnected from operational reality.

idlekube is a small experiment to make that optimization potential easier to see.

## Screenshot

![idlekube terminal output](docs/screenshot.png)

## What it does

idlekube scans your Kubernetes cluster and shows:

- cluster-level resource efficiency
- estimated monthly and annual optimization potential
- namespace summary
- workload optimization priorities
- suggested next actions
- missing ownership labels

## Requirements

- Python 3.10+
- Kubernetes cluster access
- kubeconfig configured locally
- metrics-server installed in the cluster

## Install

```bash
pip install -r requirements.txt
```

## Usage

Default pricing model:

```bash
python src/main.py scan
```

Custom pricing model:

```bash
python src/main.py scan --cpu-cost 25 --memory-cost 4
```

## Pricing model

By default:

- CPU: $25 per CPU core / month
- Memory: $4 per GB / month

These are rough defaults. Use your own numbers for more realistic estimates.

## Important note

idlekube uses current metrics-server data.

That means the output is a snapshot, not a long-term utilization analysis.

Do not blindly lower production requests based only on this output.
Use it for prioritization, then validate with longer historical data from Prometheus, OpenCost or your observability platform.

## Roadmap

Possible future improvements:

- Prometheus historical usage window
- p95 / p99 utilization
- OpenCost integration
- deployment change correlation
- owner/team mapping
- JSON export
- recommendation confidence score

## License

MIT
