# ============================================================================
# Agentic AI Platform - Bare Metal Talos Cluster
# ============================================================================
# This configuration manages Talos OS on bare metal hardware (UM690L)
# Hardware must be manually booted from Talos ISO before applying this config
# ============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    talos = {
      source  = "siderolabs/talos"
      version = "~> 0.7.0"
    }
  }
}

# Talos Provider
provider "talos" {}

# ============================================================================
# Talos Machine Configuration
# ============================================================================

# Generate machine secrets
resource "talos_machine_secrets" "this" {
  talos_version = var.talos_version
}

# Machine configuration for bare metal single-node cluster
data "talos_machine_configuration" "this" {
  cluster_name     = var.cluster_name
  cluster_endpoint = "https://${var.node_ip}:6443"
  machine_type     = "controlplane"
  machine_secrets  = talos_machine_secrets.this.machine_secrets

  talos_version      = var.talos_version
  kubernetes_version = var.kubernetes_version

  config_patches = [
    yamlencode({
      machine = {
        install = {
          # Factory image with AMD GPU extensions (amdgpu + amd-ucode)
          # Schematic: https://factory.talos.dev/schematics/b6ab12edc37d4a92a0705f4f2f12952d5a1a3f38b51783422b56810b60e230fd
          image = "factory.talos.dev/installer/b6ab12edc37d4a92a0705f4f2f12952d5a1a3f38b51783422b56810b60e230fd:${var.talos_version}"
          wipe  = true  # Force clean install
          # Use stable disk selector by model name (survives reboots)
          diskSelector = {
            model = "Samsung*"  # 250GB Samsung SSD for OS
          }
        }
        network = {
          hostname = var.node_hostname
          interfaces = [{
            interface = var.network_interface
            addresses = ["${var.node_ip}/${var.network_cidr}"]
            routes = [{
              network = "0.0.0.0/0"
              gateway = var.network_gateway
            }]
          }]
          nameservers = var.dns_servers
        }
        # AMD GPU support - load amdgpu kernel module
        kernel = {
          modules = [{
            name = "amdgpu"
          }]
        }
        sysctls = {
          # Optimize for AI workloads
          "vm.max_map_count" = "262144"  # For Qdrant
          "fs.inotify.max_user_watches" = "524288"
          # Required for Coroot node agent eBPF tracing
          "net.netfilter.nf_conntrack_events" = "1"
        }
      }
      cluster = {
        allowSchedulingOnControlPlanes = true  # Single-node - schedule workloads on CP
        network = {
          cni = {
            name = "none"  # Will deploy Cilium via ArgoCD
          }
          # Pod CIDR
          podSubnets = ["10.244.0.0/16"]
          # Service CIDR
          serviceSubnets = ["10.96.0.0/12"]
        }
        # Proxy configuration
        proxy = {
          disabled = false
        }
      }
    }),

    # Storage disk configuration patch
    # NOTE: NVMe disk names can swap on reboot - current mapping:
    # nvme0n1 = 1TB Kingston (storage), nvme1n1 = 250GB Samsung (OS)
    yamlencode({
      machine = {
        # Format and mount 1TB data drive
        # Using /dev/disk/by-id/ paths for stability would be ideal
        # but Talos requires device path. We'll handle this post-install.
        disks = [{
          device = "/dev/nvme0n1"  # 1TB Kingston (current mapping)
          partitions = [{
            mountpoint = "/var/mnt/storage"
          }]
        }]

        # Kubelet configuration for mount propagation (CRITICAL!)
        kubelet = {
          extraMounts = [{
            destination = "/var/mnt/storage"
            type        = "bind"
            source      = "/var/mnt/storage"
            options     = ["bind", "rshared", "rw"]
          }]
        }
      }
    })
  ]
}

# Generate client configuration
data "talos_client_configuration" "this" {
  cluster_name         = var.cluster_name
  client_configuration = talos_machine_secrets.this.client_configuration
  endpoints            = [var.node_ip]
  nodes                = [var.node_ip]
}

# ============================================================================
# Talos Bootstrap (After Manual ISO Boot)
# ============================================================================

# Apply machine configuration to bare metal node
resource "talos_machine_configuration_apply" "this" {
  client_configuration        = talos_machine_secrets.this.client_configuration
  machine_configuration_input = data.talos_machine_configuration.this.machine_configuration
  node                        = var.node_ip
  endpoint                    = var.node_ip

  # Manual prerequisite: Boot UM690L from Talos ISO
  # The machine will be in maintenance mode waiting for configuration
}

# Bootstrap Kubernetes cluster
resource "talos_machine_bootstrap" "this" {
  client_configuration = talos_machine_secrets.this.client_configuration
  endpoint             = var.node_ip
  node                 = var.node_ip

  depends_on = [
    talos_machine_configuration_apply.this
  ]
}

# ============================================================================
# Kubeconfig Generation
# ============================================================================

# Generate kubeconfig
data "talos_cluster_kubeconfig" "this" {
  client_configuration = talos_machine_secrets.this.client_configuration
  endpoint             = var.node_ip
  node                 = var.node_ip

  depends_on = [
    talos_machine_bootstrap.this
  ]
}

# Save kubeconfig to file
resource "local_file" "kubeconfig" {
  content         = data.talos_cluster_kubeconfig.this.kubeconfig_raw
  filename        = "${path.module}/generated/kubeconfig"
  file_permission = "0600"

  depends_on = [
    data.talos_cluster_kubeconfig.this
  ]
}

# Save talosconfig to file
resource "local_file" "talosconfig" {
  content         = data.talos_client_configuration.this.talos_config
  filename        = "${path.module}/generated/talosconfig"
  file_permission = "0600"
}

# Save machine configuration for reference
resource "local_file" "machine_config" {
  content         = data.talos_machine_configuration.this.machine_configuration
  filename        = "${path.module}/generated/machine-config.yaml"
  file_permission = "0600"
}
