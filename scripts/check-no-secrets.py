#!/usr/bin/env python3
"""Reject likely secrets from staged files."""
from __future__ import annotations
import re
import subprocess
import sys

BAD_NAMES = re.compile(r'(^|/)(\.env|.*(?:secret|credential|token|password|key).*)$', re.I)
ASSIGNMENT = re.compile(r'(?im)^\s*(?:api[_-]?key|password|secret|token)\s*[:=]\s*\S+')
OPAQUE = re.compile(r'\b(?:ghp_|hf_|sk-)[A-Za-z0-9_-]{16,}\b')
paths = subprocess.check_output(
    ['git', 'diff', '--cached', '--diff-filter=ACMR', '--name-only', '-z']
).split(b'\0')
for raw in paths:
    if not raw:
        continue
    path = raw.decode()
    if path.endswith('.env.example'):
        continue
    if BAD_NAMES.search(path) and path != 'scripts/check-no-secrets.py':
        raise SystemExit(f'refusing credential-like staged filename: {path}')
    content = subprocess.check_output(['git', 'show', f':{path}'], text=True, errors='replace')
    if ASSIGNMENT.search(content) or OPAQUE.search(content):
        raise SystemExit(f'refusing likely secret in staged file: {path}')
print(f'secret scan passed ({len([p for p in paths if p])} staged paths)')
