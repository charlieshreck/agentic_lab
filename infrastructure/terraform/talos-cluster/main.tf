# ============================================================================
# Agentic AI Platform - Single-Node Talos Cluster
# ============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.70.0"
    }
    talos = {
      source  = "siderolabs/talos"
      version = "~> 0.7.0"
    }
  }
}

# Proxmox Provider
provider "proxmox" {
  endpoint = "https://${var.proxmox_host}:8006"
  username = var.proxmox_user
  password = var.proxmox_password
  insecure = true

  ssh {
    agent    = false
    username = "root"
    password = var.proxmox_password
  }
}

# Talos Provider
provider "talos" {}

# ============================================================================
# Download Talos ISO
# ============================================================================

resource "proxmox_virtual_environment_download_file" "talos_nocloud_image" {
  content_type = "iso"
  datastore_id = var.proxmox_iso_storage
  node_name    = var.proxmox_node

  # Official Talos nocloud image (generic, no extensions needed for single-node)
  url = "https://factory.talos.dev/image/ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515/${var.talos_version}/nocloud-amd64.iso"

  file_name               = "talos-${var.talos_version}-nocloud-amd64.iso"
  overwrite               = false
  overwrite_unmanaged     = true
  checksum                = null
  checksum_algorithm      = null
}

# ============================================================================
# Talos VM
# ============================================================================

resource "proxmox_virtual_environment_vm" "talos" {
  name        = var.vm_name
  description = "Talos Linux single-node cluster for Agentic AI Platform"
  node_name   = var.proxmox_node
  vm_id       = var.vm_id

  cpu {
    cores = var.vm_cores
    type  = "host"
  }

  memory {
    dedicated = var.vm_memory
  }

  bios = "ovmf"

  efi_disk {
    datastore_id = var.proxmox_storage
    file_format  = "raw"
    type         = "4m"
  }

  # Network interface
  network_device {
    bridge      = var.network_bridge
    mac_address = var.vm_mac_address
    model       = "virtio"
  }

  # Boot disk
  disk {
    datastore_id = var.proxmox_storage
    interface    = "scsi0"
    size         = var.vm_disk_size
    file_format  = "raw"
    ssd          = true
    discard      = "on"
  }

  # Talos ISO
  cdrom {
    enabled   = true
    file_id   = proxmox_virtual_environment_download_file.talos_nocloud_image.id
    interface = "ide2"
  }

  serial_device {}

  on_boot = true
  started = true

  operating_system {
    type = "l26"  # Linux 2.6+ kernel
  }

  agent {
    enabled = false  # Talos doesn't use QEMU agent
  }

  lifecycle {
    ignore_changes = [
      cdrom,  # Prevent accidental ISO unmounting
    ]
  }
}

# ============================================================================
# Talos Machine Configuration
# ============================================================================

# Generate machine secrets
resource "talos_machine_secrets" "this" {
  talos_version = var.talos_version
}

# Machine configuration for single-node cluster (acts as both CP and worker)
data "talos_machine_configuration" "this" {
  cluster_name     = var.cluster_name
  cluster_endpoint = "https://${var.vm_ip}:6443"
  machine_type     = "controlplane"
  machine_secrets  = talos_machine_secrets.this.machine_secrets

  talos_version      = var.talos_version
  kubernetes_version = var.kubernetes_version

  docs_enabled = false
  examples_enabled = false

  config_patches = [
    yamlencode({
      machine = {
        install = {
          disk = "/dev/sda"
          image = "factory.talos.dev/installer/ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515:${var.talos_version}"
        }
        network = {
          hostname = var.vm_name
          interfaces = [{
            interface = "eth0"
            addresses = ["${var.vm_ip}/24"]
            routes = [{
              network = "0.0.0.0/0"
              gateway = var.network_gateway
            }]
          }]
          nameservers = var.dns_servers
        }
      }
      cluster = {
        allowSchedulingOnControlPlanes = true  # Single-node - schedule workloads on CP
        network = {
          cni = {
            name = "none"  # Will deploy Cilium via ArgoCD
          }
        }
      }
    })
  ]
}

# Generate client configuration
data "talos_client_configuration" "this" {
  cluster_name         = var.cluster_name
  client_configuration = talos_machine_secrets.this.client_configuration
  endpoints            = [var.vm_ip]
  nodes                = [var.vm_ip]
}

# ============================================================================
# Talos Bootstrap
# ============================================================================

# Apply machine configuration to VM
resource "talos_machine_configuration_apply" "this" {
  client_configuration        = talos_machine_secrets.this.client_configuration
  machine_configuration_input = data.talos_machine_configuration.this.machine_configuration
  node                        = var.vm_ip
  endpoint                    = var.vm_ip

  # Apply after VM is created and booted
  depends_on = [
    proxmox_virtual_environment_vm.talos
  ]
}

# Bootstrap Kubernetes cluster
resource "talos_machine_bootstrap" "this" {
  client_configuration = talos_machine_secrets.this.client_configuration
  endpoint             = var.vm_ip
  node                 = var.vm_ip

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
  endpoint             = var.vm_ip
  node                 = var.vm_ip

  depends_on = [
    talos_machine_bootstrap.this
  ]
}

# Save kubeconfig to file
resource "local_file" "kubeconfig" {
  content         = data.talos_cluster_kubeconfig.this.kubeconfig_raw
  filename        = "${path.module}/generated/kubeconfig"
  file_permission = "0600"
}

# Save talosconfig to file
resource "local_file" "talosconfig" {
  content         = data.talos_client_configuration.this.talos_config
  filename        = "${path.module}/generated/talosconfig"
  file_permission = "0600"
}
