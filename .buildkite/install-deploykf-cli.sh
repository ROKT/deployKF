#!/usr/bin/env bash
# Install deploykf CLI from GitHub releases into .buildkite/bin/
set -euo pipefail

DEPLOYKF_CLI_VERSION="${DEPLOYKF_CLI_VERSION:-v0.1.2}"
BASE_URL="https://github.com/deployKF/cli/releases/download/${DEPLOYKF_CLI_VERSION}"

# Map uname to release asset suffix (deploykf-OS-ARCH)
OS="$(uname -s)"
ARCH="$(uname -m)"
case "$OS" in
  Darwin)  OS=darwin ;;
  Linux)   OS=linux ;;
  *)       echo "Unsupported OS: $OS" >&2; exit 1 ;;
esac
case "$ARCH" in
  x86_64)  ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *)       echo "Unsupported ARCH: $ARCH" >&2; exit 1 ;;
esac

BINARY_NAME="deploykf-${OS}-${ARCH}"
INSTALL_DIR=".buildkite/bin"
mkdir -p "$INSTALL_DIR"

echo "Installing deploykf CLI ${DEPLOYKF_CLI_VERSION} (${BINARY_NAME})..."
curl -fsSL -o "${INSTALL_DIR}/deploykf" "${BASE_URL}/${BINARY_NAME}"
chmod +x "${INSTALL_DIR}/deploykf"

"${INSTALL_DIR}/deploykf" version || true
