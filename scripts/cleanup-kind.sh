#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="shepherd-e2e"
echo "==> Deleting Kind cluster '${CLUSTER_NAME}'..."
kind delete cluster --name "${CLUSTER_NAME}" || true
echo "Cleanup complete."
