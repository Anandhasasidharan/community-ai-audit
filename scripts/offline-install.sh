#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# offline-install.sh — Install community-ai-audit from an air-gapped bundle
#
# Usage:
#   bash offline-install.sh /path/to/community-ai-audit-airgap-v0.4.0.tar.gz
#
# The script extracts the tarball and offers three install strategies:
#   1. pip install (from pre-built wheels or source)
#   2. docker load
#   3. helm install
# ============================================================================

# --- Usage / help -----------------------------------------------------------
usage() {
    cat >&2 <<-EOF
Usage: $(basename "$0") <path-to-airgap-tarball>

Extract and install community-ai-audit from an offline bundle.

ARGUMENTS
  <path-to-airgap-tarball>   Path to the .tar.gz airgap bundle

EXAMPLES
  bash $(basename "$0") ~/community-ai-audit-airgap-v0.4.0.tar.gz
EOF
    exit 1
}

# --- Parse arguments --------------------------------------------------------
if [[ $# -ne 1 ]]; then
    usage
fi

TARBALL="$1"
if [[ ! -f "${TARBALL}" ]]; then
    echo "ERROR: File not found: ${TARBALL}" >&2
    exit 1
fi

# --- Determine bundle name and working directory ----------------------------
echo "[1/4] Extracting bundle from ${TARBALL}"

# The top-level directory inside the tarball is the bundle name.
BUNDLE_NAME="$(tar -tzf "${TARBALL}" | head -1 | cut -d/ -f1)"
if [[ -z "${BUNDLE_NAME}" ]]; then
    echo "ERROR: Cannot determine bundle name from tarball." >&2
    exit 1
fi

WORK_DIR="$(mktemp -d)"
# Clean up the temp directory on exit
cleanup() {
    rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

tar -xzf "${TARBALL}" -C "${WORK_DIR}"
BUNDLE_DIR="${WORK_DIR}/${BUNDLE_NAME}"

if [[ ! -d "${BUNDLE_DIR}" ]]; then
    echo "ERROR: Extracted bundle directory not found: ${BUNDLE_DIR}" >&2
    exit 1
fi

cd "${BUNDLE_DIR}"
echo "  Extracted to: ${BUNDLE_DIR}"

# ---------------------------------------------------------------------------
# Helper: detect available installation methods
# ---------------------------------------------------------------------------
HAS_WHEELS=false
HAS_DOCKERFILE=false
HAS_DOCKER_IMAGE=false
HAS_HELM=false

if [[ -d wheels ]] && ls wheels/*.whl &>/dev/null 2>&1; then
    HAS_WHEELS=true
fi
if [[ -f Dockerfile ]]; then
    HAS_DOCKERFILE=true
fi
if [[ -f community-ai-audit-image.tar ]]; then
    HAS_DOCKER_IMAGE=true
fi
if [[ -d charts/community-ai-audit ]]; then
    HAS_HELM=true
fi

echo "[2/4] Detecting available install methods"
echo "  - Pre-built wheels:         ${HAS_WHEELS}"
echo "  - Dockerfile:               ${HAS_DOCKERFILE}"
echo "  - Docker saved image:       ${HAS_DOCKER_IMAGE}"
echo "  - Helm chart:               ${HAS_HELM}"

# ---------------------------------------------------------------------------
# Install functions
# ---------------------------------------------------------------------------
install_pip() {
    echo ""
    echo "--- Installing via pip ---"

    if [[ "${HAS_WHEELS}" == true ]]; then
        echo "  Installing from pre-built wheels..."
        pip install --no-index --find-links ./wheels -r requirements.txt
        pip install --no-index --find-links ./wheels .
    else
        echo "  No pre-built wheels found. Building from source..."
        if command -v pip &>/dev/null; then
            pip install --upgrade pip setuptools wheel 2>/dev/null || true
            pip install -r requirements.txt 2>/dev/null || true
            pip install .
        else
            echo "  WARNING: pip is not available. Skipping pip install." >&2
            return 1
        fi
    fi
    echo "  pip install completed."
}

install_docker() {
    echo ""
    echo "--- Installing via Docker ---"

    if [[ "${HAS_DOCKER_IMAGE}" == true ]]; then
        echo "  Loading Docker image from community-ai-audit-image.tar..."
        docker load < community-ai-audit-image.tar
    elif [[ "${HAS_DOCKERFILE}" == true ]]; then
        echo "  Building Docker image from Dockerfile..."
        docker build -t "community-ai-audit:${BUNDLE_VERSION:-latest}" .
    else
        echo "  WARNING: Neither Dockerfile nor saved image found. Skipping." >&2
        return 1
    fi
    echo "  Docker install completed."
}

install_helm() {
    echo ""
    echo "--- Installing via Helm ---"

    if [[ "${HAS_HELM}" == true ]]; then
        if command -v helm &>/dev/null; then
            helm install community-ai-audit ./charts/community-ai-audit/
            echo "  Helm install completed."
        else
            echo "  WARNING: helm CLI not found. Skipping Helm install." >&2
            return 1
        fi
    else
        echo "  WARNING: Helm chart not found. Skipping." >&2
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Prompt user for install method
# ---------------------------------------------------------------------------
echo "[3/4] Choose installation method:"
echo ""
echo "  1) pip install   (Python package — CLI tool)"
echo "  2) docker load   (Docker container)"
echo "  3) helm install  (Kubernetes / Helm chart)"
echo "  4) all of the above"
echo "  q) quit (no installation)"
echo ""

INSTALL_METHODS=()
read -r -p "Enter your choice [1/2/3/4/q]: " CHOICE
case "${CHOICE}" in
    1) INSTALL_METHODS=(pip) ;;
    2) INSTALL_METHODS=(docker) ;;
    3) INSTALL_METHODS=(helm) ;;
    4) INSTALL_METHODS=(pip docker helm) ;;
    q|Q) echo "Exiting."; exit 0 ;;
    *)  echo "Invalid choice. Exiting." >&2; exit 1 ;;
esac

for method in "${INSTALL_METHODS[@]}"; do
    case "${method}" in
        pip)    install_pip    || true ;;
        docker) install_docker || true ;;
        helm)   install_helm   || true ;;
    esac
done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
echo "[4/4] Validating installation"
echo ""

if command -v community-ai-audit &>/dev/null; then
    echo "  community-ai-audit binary found:"
    community-ai-audit --version 2>&1 || echo "  (version flag not available — binary is present)"
elif docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q community-ai-audit; then
    echo "  Docker image community-ai-audit is loaded:"
    docker images community-ai-audit
else
    echo "  WARNING: community-ai-audit was not found in PATH. If you installed" >&2
    echo "  via Docker or Helm, ensure the container/pod is running." >&2
fi

echo ""
echo "Installation complete. See ${BUNDLE_NAME}/README.txt for more details."
