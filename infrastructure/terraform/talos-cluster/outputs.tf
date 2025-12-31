# ============================================================================
# Terraform Outputs - Agentic AI Platform
# ============================================================================

output "cluster_name" {
  description = "Kubernetes cluster name"
  value       = var.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = "https://${var.vm_ip}:6443"
}

output "vm_ip" {
  description = "Talos VM IP address"
  value       = var.vm_ip
}

output "vm_id" {
  description = "Proxmox VM ID"
  value       = var.vm_id
}

output "kubeconfig_path" {
  description = "Path to generated kubeconfig file"
  value       = abspath("${path.module}/generated/kubeconfig")
}

output "talosconfig_path" {
  description = "Path to generated talosconfig file"
  value       = abspath("${path.module}/generated/talosconfig")
}

output "talos_version" {
  description = "Talos Linux version"
  value       = var.talos_version
}

output "kubernetes_version" {
  description = "Kubernetes version"
  value       = var.kubernetes_version
}

output "next_steps" {
  description = "Commands to run after terraform apply"
  value       = <<-EOT

    ✅ Talos cluster provisioned successfully!

    Next steps:

    1. Export kubeconfig:
       export KUBECONFIG=${abspath("${path.module}/generated/kubeconfig")}

    2. Export talosconfig:
       export TALOSCONFIG=${abspath("${path.module}/generated/talosconfig")}

    3. Verify cluster health:
       kubectl get nodes
       talosctl health --nodes ${var.vm_ip}

    4. Deploy ArgoCD:
       cd ../../../kubernetes/bootstrap
       kubectl apply -k .

    5. Access ArgoCD:
       kubectl -n argocd get secret argocd-initial-admin-secret \
         -o jsonpath="{.data.password}" | base64 -d
       kubectl port-forward svc/argocd-server -n argocd 8080:443
       # Open: https://localhost:8080 (admin / password from above)

    See PHASES.md for complete implementation roadmap.
  EOT
}
