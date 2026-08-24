#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="sre-ai-e2e"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> [1/4] Checking Container Runtime..."
if ! docker ps >/dev/null 2>&1; then
    if command -v colima >/dev/null 2>&1; then
        echo "Starting Colima..."
        colima start --cpu 2 --memory 4
    elif command -v orb >/dev/null 2>&1; then
        echo "Starting OrbStack..."
        orb start
    else
        echo "Error: Docker daemon is not reachable. Please start Docker / Colima / OrbStack."
        exit 1
    fi
fi

echo "==> [2/4] Checking Kind Cluster '${CLUSTER_NAME}'..."
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo "Creating Kind cluster '${CLUSTER_NAME}'..."
    kind create cluster --name "${CLUSTER_NAME}" --wait 60s
else
    echo "Kind cluster '${CLUSTER_NAME}' already running."
fi

kubectl cluster-info --context "kind-${CLUSTER_NAME}"

echo "==> [3/4] Deploying Incident Scenario (OOMKilled & CrashLoopBackOff)..."
kubectl apply -f "${ROOT_DIR}/manifests/scenario-oom-incident.yaml"

echo "==> [4/4] Waiting for pods to initialize and trigger OOMKill..."
echo "Waiting 15 seconds for order-api pods to exceed 32Mi memory limit..."
sleep 15

echo ""
echo "================================================================="
echo "Live Pod Status in 'ecommerce-demo' Namespace:"
echo "================================================================="
kubectl get pods -n ecommerce-demo -o wide
echo ""
echo "Recent Warning Events:"
kubectl get events -n ecommerce-demo --field-selector type=Warning --sort-by='.metadata.creationTimestamp' | tail -n 5 || true
echo "================================================================="
echo ""
echo "Setup complete! Now run the E2E incident investigation with:"
echo "  python scripts/run-e2e-incident.py"
