#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# airgap-bundle.sh — Create an air-gapped offline bundle for community-ai-audit
#
# Usage:
#   bash airgap-bundle.sh
#
# Run this from within the community-ai-audit repository root (or from
# the scripts/ directory).  A tarball named
#   community-ai-audit-airgap-v0.4.0.tar.gz
# will be created in the current working directory.
# ============================================================================

BUNDLE_VERSION="0.4.0"
BUNDLE_NAME="community-ai-audit-airgap-v${BUNDLE_VERSION}"
ARCHIVE="${BUNDLE_NAME}.tar.gz"

# --- Locate the project root -------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/../pyproject.toml" ]]; then
    PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
elif [[ -f "${PWD}/pyproject.toml" ]]; then
    PROJECT_ROOT="${PWD}"
else
    echo "ERROR: Cannot find project root (pyproject.toml not found)." >&2
    echo "Run this script from inside the community-ai-audit repository." >&2
    exit 1
fi

echo "[1/6] Creating bundle directory: ${BUNDLE_NAME}"
BUNDLE_DIR="${PWD}/${BUNDLE_NAME}"
rm -rf "${BUNDLE_DIR}"
mkdir -p "${BUNDLE_DIR}"

echo "[2/6] Copying project source and configuration"
# Project source code
cp -r "${PROJECT_ROOT}/community_ai_audit" "${BUNDLE_DIR}/community_ai_audit"
# Docker assets
cp "${PROJECT_ROOT}/Dockerfile" "${BUNDLE_DIR}/"
cp "${PROJECT_ROOT}/docker-compose.yml" "${BUNDLE_DIR}/"
# Configuration
cp -r "${PROJECT_ROOT}/config" "${BUNDLE_DIR}/config"
# Project metadata (required to build/install the Python package)
cp "${PROJECT_ROOT}/pyproject.toml" "${BUNDLE_DIR}/"
cp "${PROJECT_ROOT}/README.md" "${BUNDLE_DIR}/"
cp "${PROJECT_ROOT}/LICENSE" "${BUNDLE_DIR}/" 2>/dev/null || true
# Helm chart
if [[ -d "${PROJECT_ROOT}/charts" ]]; then
    cp -r "${PROJECT_ROOT}/charts" "${BUNDLE_DIR}/charts"
fi

echo "[3/6] Generating requirements.txt from pyproject.toml"
python3 -c "
import re, sys
try:
    import tomllib
    with open('${PROJECT_ROOT}/pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
except ImportError:
    try:
        import toml
        with open('${PROJECT_ROOT}/pyproject.toml') as f:
            data = toml.load(f)
    except ImportError:
        sys.exit(2)

deps = data.get('project', {}).get('dependencies', [])
with open('${BUNDLE_DIR}/requirements.txt', 'w') as out:
    for dep in deps:
        out.write(dep.strip() + '\n')
print('OK')
" 2>/dev/null || {
    echo "  (fallback: extracting dependencies with grep)"
    grep -E '^\s+'${PROJECT_ROOT}/pyproject.toml \
        | sed -n '/^dependencies = \[/,/^\]/p' \
        | sed 's/^[[:space:]]*//; s/,$//; s/"//g; /^\[/d; /^\]/d' \
        > "${BUNDLE_DIR}/requirements.txt" 2>/dev/null || true
}

echo "[4/6] Capturing pinned dependencies (pip freeze → requirements-offline.txt)"
# Run pip freeze inside the project environment if possible, otherwise warn.
if command -v pip &>/dev/null; then
    pip freeze --all 2>/dev/null > "${BUNDLE_DIR}/requirements-offline.txt" || \
    pip freeze 2>/dev/null > "${BUNDLE_DIR}/requirements-offline.txt" || {
        echo "  WARNING: pip freeze failed; writing placeholder." >&2
        echo "# requirements-offline.txt could not be auto-generated." > "${BUNDLE_DIR}/requirements-offline.txt"
        echo "# Re-run this script inside a virtual environment where the package is installed." >> "${BUNDLE_DIR}/requirements-offline.txt"
    }
else
    echo "  WARNING: pip not found; writing placeholder." >&2
    echo "# requirements-offline.txt could not be auto-generated (pip not available)." > "${BUNDLE_DIR}/requirements-offline.txt"
fi

echo "[5/6] Creating README.txt with install instructions"
cat > "${BUNDLE_DIR}/README.txt" <<- README_EOF
================================================================================
 community-ai-audit — Offline / Air-Gapped Installation Bundle v${BUNDLE_VERSION}
================================================================================

This bundle contains everything needed to install and run
community-ai-audit on a machine without internet access.

WHAT'S INCLUDED
---------------
  community_ai_audit/       — Python package source code
  Dockerfile                — Container image definition
  docker-compose.yml        — Docker Compose configuration
  config/                   — Configuration files
  charts/                   — Helm chart for Kubernetes deployment
  pyproject.toml            — Python build/project metadata
  requirements.txt          — Direct Python dependencies
  requirements-offline.txt  — Fully pinned dependencies (pip freeze)

INSTALLATION OPTIONS
--------------------

### Option A — Python / pip (recommended for direct CLI use)

  1. (On internet-connected machine) Pre-build wheels:
       pip wheel --wheel-dir=./wheels -r requirements-offline.txt

  2. Transfer the bundle to the air-gapped machine.

  3. Install from offline wheels:
       pip install --no-index --find-links ./wheels -r requirements.txt
       pip install --no-index --find-links ./wheels .

  Or use the helper:
       bash offline-install.sh /path/to/${ARCHIVE}

### Option B — Docker

  1. Build the image on an internet-connected machine:
       docker build -t community-ai-audit:${BUNDLE_VERSION} .

  2. Save and transfer the image:
       docker save -o community-ai-audit-image.tar community-ai-audit:${BUNDLE_VERSION}

  3. Load on the air-gapped machine:
       docker load < community-ai-audit-image.tar

### Option C — Helm / Kubernetes

  1. Transfer the bundle to the air-gapped Kubernetes node.

  2. Install with Helm:
       helm install community-ai-audit ./charts/community-ai-audit/

VERIFY THE INSTALLATION
-----------------------
  community-ai-audit --version

For more details, see the project README and documentation at:
  https://github.com/anomalyco/community-ai-audit
================================================================================
README_EOF

echo "[6/6] Creating archive: ${ARCHIVE}"
tar -czf "${ARCHIVE}" "${BUNDLE_NAME}"

echo ""
echo "SUCCESS: Air-gap bundle created at: ${PWD}/${ARCHIVE}"
echo "         Size: $(du -h "${ARCHIVE}" | cut -f1)"
echo ""
echo "To distribute, copy ${ARCHIVE} to the air-gapped machine and run:"
echo "  tar -xzf ${ARCHIVE}"
echo "  cd ${BUNDLE_NAME}"
echo "  bash offline-install.sh"
