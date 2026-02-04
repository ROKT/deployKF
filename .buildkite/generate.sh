#!/usr/bin/env bash
# Install deploykf CLI and run generate. Ensures the generate step uses a known CLI version.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

.buildkite/install-deploykf-cli.sh
export PATH="$(pwd)/.buildkite/bin:${PATH}"

deploykf generate \
  --source-path ./generator \
  --values ./sample-values.yaml \
  --values ./sample-values-overrides.yaml \
  --values .buildkite/ci-argocd-placeholder.yaml \
  --output-dir ./GENERATOR_OUTPUT

tar czf GENERATOR_OUTPUT.tar.gz -C . GENERATOR_OUTPUT
