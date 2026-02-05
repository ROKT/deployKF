# Kubeflow Tools Upgrade (deployKF generator)

Upgrade one or more Kubeflow “kubeflow-tools” components in `deployKF` by:
- pinning to a specific upstream commit in `kubeflow/manifests`
- vendoring the upstream manifests into `generator/templates/.../upstream/`
- updating generator `kustomization.yaml` resource paths
- validating with `deploykf generate` and `kustomize build`

This skill is optimized for repeatable upgrades and avoids common pitfalls with `kustomize` remote fetch/localize and sandbox restrictions.

---

## Inputs you must decide up front

- **Target upstream commit**: the git SHA in `kubeflow/manifests` you want to pin to.
  - Example (used previously): `d8d643f1a736b28c525bd9b8ee5c9b2f4a661b39` (Kubeflow Manifests v1.10.2 era).
- **Components to upgrade**: e.g.
  - `generator/templates/manifests/kubeflow-tools/notebooks/jupyter-web-app`
  - `generator/templates/manifests/kubeflow-tools/notebooks/notebook-controller`
  - `generator/templates/manifests/kubeflow-tools/poddefaults-webhook`
  - `generator/templates/manifests/kubeflow-tools/tensorboards/tensorboards-web-app`
  - `generator/templates/manifests/kubeflow-tools/tensorboards/tensorboard-controller`

---

## Step 0 — Snapshot the “pattern” from a known-upgraded component

Pick a component that’s already upgraded (e.g. `volumes-web-app`) and note:
- the **pinned `UPSTREAM_REF`**
- whether the upstream path lives under `apps/...` or `applications/...`
- any local patches or resource overlays that must keep working

Useful commands:

```bash
git log -n 20 --oneline --decorate
git log -n 10 --name-only --pretty=format:'%h %s'
```

---

## Step 1 — Prepare a safe temp clone of `kubeflow/manifests` (recommended)

Remote kustomize fetch/localize can fail due to sandbox/git-init restrictions. The safest approach is:
1) clone upstream into a workspace temp directory
2) check out the exact pinned commit
3) copy the required subtrees into each component’s `upstream/` folder

```bash
mkdir -p tmp/upstream-manifests
rm -rf tmp/upstream-manifests/manifests

git clone --filter=blob:none --no-checkout https://github.com/kubeflow/manifests.git tmp/upstream-manifests/manifests
cd tmp/upstream-manifests/manifests
git fetch --depth=1 origin <PINNED_SHA>
git checkout <PINNED_SHA>
```

---

## Step 2 — Discover the correct upstream overlay paths at that commit

At newer releases, many components moved from `apps/...` → `applications/...`.
Find the relevant overlay `kustomization.yaml` files:

```bash
cd tmp/upstream-manifests/manifests

# Examples (adjust patterns per component)
ls applications/jupyter/jupyter-web-app/upstream/overlays/istio/kustomization.yaml
ls applications/jupyter/notebook-controller/upstream/overlays/kubeflow/kustomization.yaml
ls applications/admission-webhook/upstream/overlays/cert-manager/kustomization.yaml
ls applications/tensorboard/tensorboard-controller/upstream/overlays/kubeflow/kustomization.yaml
ls applications/tensorboard/tensorboards-web-app/upstream/overlays/istio/kustomization.yaml
```

If the paths don’t exist, search by name:

```bash
rg -n "kind: Kustomization" -S .
rg -n "jupyter-web-app|notebook-controller|admission-webhook|tensorboard-controller|tensorboards-web-app" -S .
```

---

## Step 3 — Update each component’s `sync_upstream.sh` to pin the ref and path

For each component directory:
- set `UPSTREAM_REF="<PINNED_SHA>"`
- set `UPSTREAM_PATH="applications/.../upstream/overlays/<overlay>"` (or `apps/...` if that is correct for your chosen commit)

Example snippet:

```bash
UPSTREAM_REPO="github.com/kubeflow/manifests"
UPSTREAM_PATH="applications/jupyter/jupyter-web-app/upstream/overlays/istio"
UPSTREAM_REF="<PINNED_SHA>" # (optional comment like v1.10.2)
```

---

## Step 4 — Update each component’s generator `kustomization.yaml` resource path

For each component’s generator `kustomization.yaml`, update the `resources:` entry to match the new vendored directory layout.

Example:

```yaml
resources:
  - upstream/applications/jupyter/jupyter-web-app/upstream/overlays/istio
```

---

## Step 5 — Vendor upstream manifests into each component’s `upstream/` directory

### Recommended approach (copy from the temp clone)

This avoids remote kustomize fetch problems and is deterministic.

For each component:
- remove the old `upstream/`
- copy the exact subtree from the checked-out upstream repo

Example (repeat per component):

```bash
REPO_ROOT="$(pwd)"  # run from deployKF repo root
SRC_ROOT="$REPO_ROOT/tmp/upstream-manifests/manifests"

COMP_DIR="$REPO_ROOT/generator/templates/manifests/kubeflow-tools/notebooks/jupyter-web-app"
REL_PATH="applications/jupyter/jupyter-web-app/upstream"

rm -rf "$COMP_DIR/upstream"
mkdir -p "$COMP_DIR/upstream/$(dirname "$REL_PATH")"
cp -R "$SRC_ROOT/$REL_PATH" "$COMP_DIR/upstream/$REL_PATH"
```

### Alternative approach (run `sync_upstream.sh`)

If you prefer `sync_upstream.sh`, run it from inside the component directory and ensure it’s executable:

```bash
pushd generator/templates/manifests/kubeflow-tools/<COMPONENT_DIR>
chmod +x sync_upstream.sh
./sync_upstream.sh
popd
```

Note: if `kustomize localize` fails in your environment, use the copy approach above.

---

## Step 6 — Confirm repo changes look right

You should generally see:
- **new** vendored paths under `upstream/applications/...`
- **deleted** vendored paths under the old `upstream/apps/...` (if the component moved)

```bash
git status --porcelain=v1
git diff --stat
```

---

## Step 7 — Generate output with deployKF (include override files)

The default CLI script may ignore overrides; run explicitly:

```bash
rm -rf GENERATOR_OUTPUT
deploykf generate \
  --source-path ./generator \
  --values ./sample-values.yaml \
  --values ./sample-values-overrides.yaml \
  --output-dir ./GENERATOR_OUTPUT
```

---

## Step 8 — Verify kustomize compatibility against generated output

Always validate:

```bash
kustomize build ./GENERATOR_OUTPUT/argocd > /tmp/argocd.yaml
```

Validate each upgraded component (examples):

```bash
kustomize build ./GENERATOR_OUTPUT/manifests/kubeflow-tools/volumes/volumes-web-app > /tmp/volumes.yaml

kustomize build ./GENERATOR_OUTPUT/manifests/kubeflow-tools/notebooks/jupyter-web-app > /tmp/jupyter-web-app.yaml
kustomize build ./GENERATOR_OUTPUT/manifests/kubeflow-tools/notebooks/notebook-controller > /tmp/notebook-controller.yaml
kustomize build ./GENERATOR_OUTPUT/manifests/kubeflow-tools/poddefaults-webhook > /tmp/poddefaults-webhook.yaml
kustomize build ./GENERATOR_OUTPUT/manifests/kubeflow-tools/tensorboards/tensorboard-controller > /tmp/tensorboard-controller.yaml
kustomize build ./GENERATOR_OUTPUT/manifests/kubeflow-tools/tensorboards/tensorboards-web-app > /tmp/tensorboards-web-app.yaml
```

Warnings about deprecated kustomize fields are common upstream; failures are what matter.

---

## Step 9 — Cleanup temp upstream clone (optional but recommended)

```bash
rm -rf tmp/upstream-manifests/manifests
```

---

## Troubleshooting

### “kustomize can’t find kustomization in upstream/”
- Your generated `upstream/` root will typically not contain a `kustomization.yaml`; it will be nested under `upstream/applications/...`.
- Ensure your generator `kustomization.yaml` points at the nested overlay directory, not `upstream/` root.

### Remote kustomize fetch/localize failures
- Prefer the “temp clone + copy subtree” approach (Step 5) to avoid sandbox restrictions and git init issues.

### Execute permission denied on `sync_upstream.sh`
- Run `chmod +x sync_upstream.sh` from inside the component directory.

