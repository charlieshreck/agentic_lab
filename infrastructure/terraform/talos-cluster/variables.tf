# ============================================================================
# Agentic AI Platform - Bare Metal Talos Variables
# ============================================================================

# Network Configuration
variable "node_ip" {
  description = "Static IP address for Talos node"
  type        = string
  default     = "10.20.0.109"
}

variable "network_gateway" {
  description = "Network gateway"
  type        = string
  default     = "10.20.0.1"
}

variable "network_cidr" {
  description = "Network CIDR (e.g., 24 for /24)"
  type        = number
  default     = 24
}

variable "network_interface" {
  description = "Primary network interface name"
  type        = string
  default     = "eth0"  # Usually eth0, but check with 'ip addr' during Talos maintenance mode
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

variable "node_hostname" {
  description = "Hostname for the Talos node"
  type        = string
  default     = "agentic-01"
}

variable "talos_version" {
  description = "Talos Linux version"
  type        = string
  default     = "v1.11.5"  # Matches Factory ISO version
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = "v1.34.1"  # Compatible K8s version for Talos 1.11
}

# Disk Configuration
variable "install_disk" {
  description = "Disk device path for Talos installation"
  type        = string
  default     = "/dev/nvme0n1"  # Common for NVMe drives, adjust if needed
}

variable "disk_min_size" {
  description = "Minimum disk size in GB (for diskSelector)"
  type        = number
  default     = 400  # UM690L has 1.5TB NVMe
}

# Storage Disk Configuration
variable "storage_disk" {
  description = "Disk device path for persistent storage (1TB drive)"
  type        = string
  default     = "/dev/nvme0n1"  # 1TB drive for data
}

variable "storage_disk_min_size" {
  description = "Minimum size for storage disk validation (in GB)"
  type        = number
  default     = 900  # 1TB drive should be >900GB
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
