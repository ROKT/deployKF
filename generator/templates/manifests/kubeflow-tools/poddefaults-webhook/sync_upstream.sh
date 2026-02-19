#!/usr/bin/env bash

set -euo pipefail

THIS_SCRIPT_PATH=$(cd "$(dirname "$0")" && pwd)
cd "$THIS_SCRIPT_PATH"

# upstream configs
UPSTREAM_REPO="github.com/kubeflow/manifests"
UPSTREAM_PATH="applications/admission-webhook/upstream/overlays/cert-manager"
UPSTREAM_REF="d8d643f1a736b28c525bd9b8ee5c9b2f4a661b39" # v1.10.2

# output configs
OUTPUT_PATH="./upstream"

# clean the generator output directory
rm -rf "$OUTPUT_PATH"

# localize the upstream resources with kustomize
# - https://kubectl.docs.kubernetes.io/references/kustomize/cmd/localize/
kustomize localize "${UPSTREAM_REPO}/${UPSTREAM_PATH}?ref=${UPSTREAM_REF}" "$OUTPUT_PATH" --no-verify
