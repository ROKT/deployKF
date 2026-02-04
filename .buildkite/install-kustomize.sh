#!/usr/bin/env bash
# Install kustomize into .buildkite/bin/ so kustomize build steps have it on PATH.
set -euo pipefail

KUSTOMIZE_VERSION="${KUSTOMIZE_VERSION:-5.4.2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${SCRIPT_DIR}/bin"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo "Installing kustomize ${KUSTOMIZE_VERSION}..."
curl -sL "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash -s "${KUSTOMIZE_VERSION}" .
echo "kustomize version: $(./kustomize version --short 2>/dev/null || ./kustomize version)"
