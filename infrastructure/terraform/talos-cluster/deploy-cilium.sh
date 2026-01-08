#!/bin/bash
# Deploy Cilium CNI after cluster bootstrap
# This must run BEFORE ArgoCD apps are deployed

set -e

echo "🔵 Deploying Cilium CNI..."

export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Deploy Cilium using kustomize
kubectl apply -k /home/agentic_lab/kubernetes/platform/cilium/

echo "⏳ Waiting for Cilium pods to be ready (this may take 2-3 minutes)..."
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=cilium-agent -n kube-system --timeout=300s

echo "✅ Cilium CNI deployed successfully!"
echo ""
echo "Verifying cluster networking..."
kubectl get pods -n kube-system -l app.kubernetes.io/name=cilium-agent
