variable "oci_profile" {
  type        = string
  description = "Profile name in ~/.oci/config."
  default     = "DEFAULT"
}

variable "region" {
  type        = string
  description = "Home region of the account, for example ap-hyderabad-1. Always Free resources live there."
}

variable "compartment_ocid" {
  type        = string
  description = "Compartment for every resource; the tenancy OCID works for a personal account."
  validation {
    condition     = startswith(var.compartment_ocid, "ocid1.")
    error_message = "compartment_ocid must be an OCID (ocid1...)."
  }
}

variable "ssh_public_key" {
  type        = string
  description = "Public key text (ssh-ed25519 AAAA...) for the ubuntu user."
  validation {
    condition     = startswith(var.ssh_public_key, "ssh-")
    error_message = "ssh_public_key must be a public key line, not a path or a private key."
  }
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "Who may reach port 22, for example 203.0.113.7/32 (your IP)."
  validation {
    condition     = var.ssh_allowed_cidr != "0.0.0.0/0" && can(cidrhost(var.ssh_allowed_cidr, 0))
    error_message = "Give a valid CIDR that is not 0.0.0.0/0."
  }
}

variable "availability_domain_index" {
  type        = number
  description = "Which availability domain to use (0, 1, 2). Try another when Oracle says out of host capacity."
  default     = 0
  validation {
    condition     = var.availability_domain_index >= 0 && var.availability_domain_index <= 2
    error_message = "availability_domain_index must be 0, 1 or 2."
  }
}

variable "ocpus" {
  type        = number
  description = "Ampere A1 OCPUs. The Always Free total is 2 across all instances (Oracle lowered it from 4)."
  default     = 2
  validation {
    condition     = var.ocpus >= 1 && var.ocpus <= 2
    error_message = "ocpus must be between 1 and 2 (Always Free limit)."
  }
}

variable "memory_gb" {
  type        = number
  description = "Memory in GB. The Always Free total is 12 across all instances."
  default     = 12
  validation {
    condition     = var.memory_gb >= 6 && var.memory_gb <= 12
    error_message = "memory_gb must be between 6 and 12 (Always Free limit)."
  }
}

variable "boot_volume_gb" {
  type        = number
  description = "Boot volume size. Always Free gives 200 GB of block storage in total."
  default     = 100
  validation {
    condition     = var.boot_volume_gb >= 50 && var.boot_volume_gb <= 200
    error_message = "boot_volume_gb must be between 50 and 200."
  }
}
