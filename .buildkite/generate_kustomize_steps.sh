#!/usr/bin/env bash
set -euo pipefail

# --- Configuration & Helpers -----------------------------------------------------

ARTIFACT_NAME="GENERATOR_OUTPUT"
TARBALL="${ARTIFACT_NAME}.tar.gz"

# Read roots from stdin
if [[ ! -t 0 ]]; then
  ROOTS=()
  while IFS= read -r r; do [[ -n "$r" ]] && ROOTS+=( "$r" ); done
else
  echo "Error: no roots provided" >&2
  exit 1
fi

output_filename() {
  echo "${1##*/}.yaml"
}

# --- Emit YAML pipeline -------------------------------------------------------

cat <<'EOF'
steps:
  - group: ":customs: Kustomize build"
    key: kustomize-build
    depends_on: generate
    steps:
EOF

for root in "${ROOTS[@]}"; do
  label="${root##*/}"
  outfile="$(output_filename "$root")"
  cat <<-EOF
      - label: "${label}"
        command: |
          export PATH="\$(pwd)/.buildkite/bin:\$PATH" && bash .buildkite/install-kustomize.sh
          buildkite-agent artifact download ${TARBALL} . && tar xzf ${TARBALL}
          kustomize build ./${ARTIFACT_NAME}/${root} > ${outfile}
        artifact_paths:
          - "${outfile}"
	EOF
done
