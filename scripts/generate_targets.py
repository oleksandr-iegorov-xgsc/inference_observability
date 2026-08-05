#!/usr/bin/env python3
"""Generate reviewed Prometheus file-SD definitions from Podman vLLM profiles."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODELS = Path('/opt/agent_infrastructure/podman_vllm/models')


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, value = line.split('=', 1)
        values[key] = value
    return values


def classify(model_id: str, instance: str, args: dict) -> tuple[str, str, str]:
    combined = f'{model_id} {instance}'.lower()
    if 'gemma' in combined:
        vendor, family = 'google', 'gemma4'
    elif 'qwen3.6' in combined or 'qwen36' in combined:
        vendor, family = 'alibaba', 'qwen3.6'
    elif 'qwen' in combined:
        vendor, family = 'alibaba', 'qwen3'
    elif 'gpt-oss' in combined:
        vendor, family = 'openai', 'gpt-oss'
    else:
        vendor, family = 'unknown', 'unknown'
    quantization = str(args.get('--quantization', ''))
    if not quantization:
        if 'awq-4bit' in combined:
            quantization = 'awq-int4'
        elif 'awq-8bit' in combined:
            quantization = 'awq-int8'
        elif 'awq' in combined:
            quantization = 'awq'
        elif 'gguf' in combined:
            quantization = 'gguf-q6k'
        elif 'int4' in combined:
            quantization = 'int4'
        elif 'bf16' in combined:
            quantization = 'bf16'
        else:
            quantization = 'unspecified'
    return vendor, family, quantization


def yaml_quote(value: str) -> str:
    return json.dumps(value)


def target_yaml(env: dict[str, str], args: dict, host: str) -> str:
    instance = env['INSTANCE_NAME']
    inferred_vendor, inferred_family, inferred_quantization = classify(env['MODEL_ID'], instance, args)
    vendor = env.get('MODEL_VENDOR', inferred_vendor)
    family = env.get('MODEL_FAMILY', inferred_family)
    quantization = env.get('QUANTIZATION', inferred_quantization)
    gpu_group = env.get('GPU_DEVICES', 'unknown').replace('nvidia.com/', '')
    labels = {
        'host': host,
        'model': env['SERVED_MODEL_NAME'],
        'model_vendor': vendor,
        'model_family': family,
        'vllm_instance': instance,
        'container': env['CONTAINER_NAME'],
        'gpu_group': gpu_group,
        'quantization': quantization,
        'host_port': env['HOST_PORT'],
    }
    lines = ['- targets:', f'    - {yaml_quote("127.0.0.1:" + env["HOST_PORT"])}', '  labels:']
    lines.extend(f'    {key}: {yaml_quote(value)}' for key, value in labels.items())
    return '\n'.join(lines) + '\n'


def known(models: Path, output: Path, host: str) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for env_path in sorted(models.glob('*/model.env')):
        env = parse_env(env_path)
        args_path = env_path.parent / 'vllm.args.json'
        args = json.loads(args_path.read_text())
        if not isinstance(args, dict):
            raise ValueError(f'{args_path} must contain a JSON object')
        destination = output / f'vllm-{env["INSTANCE_NAME"]}.yml'
        destination.write_text(target_yaml(env, args, host))
        result[env['CONTAINER_NAME']] = destination
    return result


def running_containers() -> set[str]:
    completed = subprocess.run(
        ['podman', 'ps', '--format', '{{.Names}}'], text=True, check=True,
        stdout=subprocess.PIPE,
    )
    return set(completed.stdout.split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--models-root', type=Path, default=DEFAULT_MODELS)
    parser.add_argument(
        '--host',
        default=os.environ.get('FLEET_HOST', socket.gethostname()),
        help='stable host label for generated targets (defaults to FLEET_HOST or local hostname)',
    )
    parser.add_argument('--all-active', action='store_true', help='activate every configured profile')
    parser.add_argument('command', choices=('generate-known', 'sync-active'))
    ns = parser.parse_args()
    known_dir = ROOT / 'prometheus' / 'targets' / 'known'
    active_dir = ROOT / 'prometheus' / 'targets' / 'active'
    profiles = known(ns.models_root, known_dir, ns.host)
    if ns.command == 'generate-known':
        print(f'generated {len(profiles)} known vLLM targets in {known_dir}')
        return
    active_dir.mkdir(parents=True, exist_ok=True)
    for path in active_dir.glob('vllm-*.yml'):
        path.unlink()
    active_names = set(profiles) if ns.all_active else running_containers()
    active = 0
    for container, source in profiles.items():
        if container in active_names:
            shutil.copy2(source, active_dir / source.name)
            active += 1
    print(f'activated {active} of {len(profiles)} known vLLM targets in {active_dir}')


if __name__ == '__main__':
    main()
