# Inference observability

Portable, rootless-Podman observability for vLLM deployments defined in `/opt/agent_infrastructure/podman_vllm`.

## Components

- Prometheus on `127.0.0.1:9090`
- Grafana on `127.0.0.1:3000`
- node_exporter on `127.0.0.1:9100`
- NVIDIA DCGM Exporter on `127.0.0.1:9400`

The vLLM backends remain private. Prometheus uses host networking to scrape their existing `127.0.0.1:<port>/metrics` endpoints; it does not restart or modify model containers.

## Model targets

`prometheus/targets/known/` contains a reviewed target definition for every profile under the serving root. `prometheus/targets/active/` is the file-SD directory actually scraped by Prometheus.

```bash
# Regenerate all known definitions and activate only currently running managed models.
./scripts/generate_targets.py sync-active

# Validation-only demonstration: activate every configured profile, including stopped ones.
./scripts/generate_targets.py --all-active sync-active
```

Run `sync-active` after starting or stopping a model. Prometheus notices active target changes without a restart. Targets receive a stable `host` label (the local hostname by default); pass `--host "$FLEET_HOST"` when a deployment uses a deliberate inventory name.

## Local secret setup

Copy `.env.example` to `.env`, set a strong Grafana password, and keep `.env` private. It is Git-ignored.

## Lifecycle

```bash
podman-compose --env-file .env -f compose.yaml up -d
./scripts/run-dcgm-exporter.sh
./scripts/validate.sh
```

`run-dcgm-exporter.sh` intentionally uses the verified NVIDIA OCI hook at `/opt/agent_infrastructure/podman_vllm/hooks`, because this host's rootless Podman 4.9.3 cannot resolve the current NVIDIA CDI device identifiers. The rest of the stack uses Compose.

## Fleet host and model selection

The provisioned **vLLM Fleet Overview** dashboard has multi-select `Host` and `Model` variables. `Host` filters all vLLM and DCGM panels, and `Model` filters the vLLM request, throughput, latency, and KV-cache panels. Every engine series retains `host`, `model`, and `vllm_instance` in its grouping, so history remains comparable after new servers are added.

GPU processing utilization, temperature, power draw, and framebuffer-memory panels use DCGM telemetry and are host-wide physical-GPU measurements. They cannot be allocated exactly to a selected model or agent when workloads share a GPU. For a tensor-parallel model, inspect each GPU series individually; do not sum utilization percentages.

## Adding another server

Run the same exporter stack on the new server, give its Prometheus targets a unique stable `host` label, and keep the vLLM `model` and `vllm_instance` labels unchanged in meaning. Aggregate the per-host Prometheus servers with federation or remote write into the Grafana datasource; do not scrape a remote server's loopback-only vLLM endpoints from this host. The `host` label is the fleet boundary, while `instance` remains the exporter endpoint and `vllm_instance` remains the logical model-server identity.

## Attribution boundary

This deployment measures model, vLLM instance, host, and GPU behavior. It does not provide per-agent measurements because agents call vLLM directly. An authenticated proxy is the future extension point for metrics labelled with `agent_id`.
