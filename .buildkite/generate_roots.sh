#!/usr/bin/env bash
# Discovers kustomize root directories under ROOT and prints them one per line.
# A "root" is a directory that contains kustomization.yaml and has no ancestor
# (in the same tree) that also contains kustomization.yaml — i.e. the topmost
# kustomization on each path.
set -euo pipefail

ROOT="${1:-GENERATOR_OUTPUT}"

if [[ ! -d "$ROOT" ]]; then
  echo "Error: directory '$ROOT' not found (run from repo root after generate, or pass path)" >&2
  exit 1
fi

ROOT="$(cd "$ROOT" && pwd)"

find "$ROOT" -type f -name kustomization.yaml -print0 |
  while IFS= read -r -d '' f; do
    d="${f%/kustomization.yaml}"
    d="${d#"$ROOT"/}"
    [[ -n "$d" ]] && printf '%s\n' "$d"
  done |
  sort -u |
  awk '
    BEGIN { last = "" }
    {
      d = $0
      # keep d only if it is NOT under the last kept directory
      if (last == "" || index(d, last "/") != 1) { print d; last = d }
    }
  '
