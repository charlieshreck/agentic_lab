# ============================================================================
# Terraform Outputs - Bare Metal Talos
# ============================================================================

output "cluster_name" {
  description = "Kubernetes cluster name"
  value       = var.cluster_name
}

output "cluster_endpoint" {
  description = "Kubernetes API endpoint"
  value       = "https://${var.node_ip}:6443"
}

output "node_ip" {
  description = "Talos node IP address"
  value       = var.node_ip
}

output "node_hostname" {
  description = "Talos node hostname"
  value       = var.node_hostname
}

output "kubeconfig_path" {
  description = "Path to generated kubeconfig file"
  value       = abspath("${path.module}/generated/kubeconfig")
}

output "talosconfig_path" {
  description = "Path to generated talosconfig file"
  value       = abspath("${path.module}/generated/talosconfig")
}

output "machine_config_path" {
  description = "Path to generated machine configuration"
  value       = abspath("${path.module}/generated/machine-config.yaml")
}

output "talos_version" {
  description = "Talos Linux version"
  value       = var.talos_version
}

output "kubernetes_version" {
  description = "Kubernetes version"
  value       = var.kubernetes_version
}

output "install_disk" {
  description = "Disk used for Talos installation"
  value       = var.install_disk
}

output "next_steps" {
  description = "Commands to run after terraform apply"
  value       = <<-EOT

    ✅ Talos bare metal cluster configured successfully!

    Next steps:

    1. Export configurations:
       export KUBECONFIG=${abspath("${path.module}/generated/kubeconfig")}
       export TALOSCONFIG=${abspath("${path.module}/generated/talosconfig")}

    2. Verify cluster health:
       kubectl get nodes
       # Should show: ${var.node_hostname} Ready control-plane

       talosctl health --nodes ${var.node_ip}
       # All health checks should pass

    3. Check system pods:
       kubectl get pods -A
       # Core components should be running

    4. Deploy CNI (Cilium) and core platform:
       cd ../../../kubernetes/bootstrap
       kubectl apply -k .

    5. Access ArgoCD:
       # Wait for ArgoCD to deploy, then:
       kubectl -n argocd get secret argocd-initial-admin-secret \
         -o jsonpath="{.data.password}" | base64 -d
       kubectl port-forward svc/argocd-server -n argocd 8080:443
       # Open: https://localhost:8080 (admin / password from above)

    6. Monitor deployment:
       kubectl get applications -n argocd
       argocd app list

    See PHASES.md for complete implementation roadmap.

    Troubleshooting:
    - Talos dashboard: talosctl dashboard --nodes ${var.node_ip}
    - Talos logs: talosctl logs -f --nodes ${var.node_ip}
    - Disk check: talosctl disks --nodes ${var.node_ip}
  EOT
}

output "storage_configuration" {
  description = "Storage disk configuration summary"
  value = {
    os_disk       = var.install_disk
    os_size_min   = var.disk_min_size
    data_disk     = var.storage_disk
    data_size_min = var.storage_disk_min_size
    mount_point   = "/var/mnt/storage"
    warning       = "VERIFY: OS=${var.install_disk} (256GB), DATA=${var.storage_disk} (1TB)"
  }
}
