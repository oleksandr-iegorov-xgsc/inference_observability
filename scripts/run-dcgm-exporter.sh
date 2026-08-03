#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="$ROOT/.env"
[[ -f $ENV_FILE ]] || { printf 'Missing %s; copy .env.example first.\n' "$ENV_FILE" >&2; exit 1; }
# .env is deployment-owned and local-only; it contains the Grafana credential.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${DCGM_EXPORTER_IMAGE:?DCGM_EXPORTER_IMAGE is required}"
: "${DCGM_EXPORTER_PORT:?DCGM_EXPORTER_PORT is required}"
: "${NVIDIA_OCI_HOOKS_DIR:=/opt/agent_infrastructure/podman_vllm/hooks}"
[[ -d $NVIDIA_OCI_HOOKS_DIR ]] || { printf 'Missing NVIDIA OCI hooks directory: %s\n' "$NVIDIA_OCI_HOOKS_DIR" >&2; exit 1; }

podman rm -f inference-dcgm-exporter >/dev/null 2>&1 || true
exec podman run -d \
  --name inference-dcgm-exporter \
  --replace \
  --restart unless-stopped \
  --network host \
  --security-opt=label=disable \
  --hooks-dir="$NVIDIA_OCI_HOOKS_DIR" \
  "$DCGM_EXPORTER_IMAGE"
