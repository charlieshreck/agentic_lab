# ============================================================================
# Agentic AI Platform - Talos Single-Node Cluster Variables
# ============================================================================

# Proxmox Connection
variable "proxmox_host" {
  description = "Proxmox host address"
  type        = string
  default     = "10.20.0.1"  # Update based on actual Proxmox host for UM690L
}

variable "proxmox_user" {
  description = "Proxmox API user"
  type        = string
  default     = "root@pam"
}

variable "proxmox_password" {
  description = "Proxmox password"
  type        = string
  sensitive   = true
}

variable "proxmox_node" {
  description = "Proxmox node name"
  type        = string
  default     = "Carrick"  # Update based on actual node name
}

# Network Configuration
variable "network_bridge" {
  description = "Network bridge for VM"
  type        = string
  default     = "vmbr0"
}

variable "network_gateway" {
  description = "Network gateway"
  type        = string
  default     = "10.20.0.1"
}

variable "dns_servers" {
  description = "DNS servers"
  type        = list(string)
  default     = ["1.1.1.1", "8.8.8.8"]
}

# Cluster Configuration
variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "agentic-platform"
}

variable "talos_version" {
  description = "Talos Linux version"
  type        = string
  default     = "v1.8.1"  # Stable version, update as needed
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "v1.31.1"  # Stable version, update as needed
}

# Storage Configuration
variable "proxmox_storage" {
  description = "Proxmox storage pool for VM disk"
  type        = string
  default     = "local-lvm"  # Update based on actual Proxmox storage
}

variable "proxmox_iso_storage" {
  description = "Proxmox storage for ISO images"
  type        = string
  default     = "local"
}

# VM Configuration
variable "vm_id" {
  description = "Proxmox VM ID"
  type        = number
  default     = 400
}

variable "vm_name" {
  description = "VM name"
  type        = string
  default     = "agentic-talos"
}

variable "vm_ip" {
  description = "Static IP address for VM"
  type        = string
  default     = "10.20.0.109"
}

variable "vm_cores" {
  description = "Number of CPU cores"
  type        = number
  default     = 8  # Use most of UM690L's 8C/16T
}

variable "vm_memory" {
  description = "RAM in MB"
  type        = number
  default     = 24576  # 24GB (leave ~8GB for host)
}

variable "vm_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 500  # 500GB for OS + models (1.5TB NVMe total)
}

# MAC Address (optional - Proxmox will auto-generate if not specified)
variable "vm_mac_address" {
  description = "MAC address for VM (optional)"
  type        = string
  default     = null
}

# GitOps Configuration
variable "gitops_repo_url" {
  description = "GitOps repository URL"
  type        = string
  default     = "https://github.com/charlieshreck/agentic_lab.git"
}

variable "gitops_repo_branch" {
  description = "GitOps repository branch"
  type        = string
  default     = "main"
}
