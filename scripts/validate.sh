#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

podman exec inference-prometheus promtool check config /etc/prometheus/prometheus.yml
curl -fsS http://127.0.0.1:9090/-/ready >/dev/null
curl -fsS http://127.0.0.1:3000/api/health >/dev/null
curl -fsS http://127.0.0.1:9400/metrics >/dev/null
curl -fsS http://127.0.0.1:9100/metrics >/dev/null
curl -fsS http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json, sys
items = json.load(sys.stdin)["data"]["activeTargets"]
down = [item for item in items if item["health"] != "up"]
if down:
    raise SystemExit("unhealthy Prometheus targets: " + repr(down))
print(f"validated {len(items)} active Prometheus targets")
'
printf 'PASS: inference observability stack is healthy.\n'
