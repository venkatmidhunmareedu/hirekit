terraform {
  required_version = ">= 1.9"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }
}

# Credentials come from ~/.oci/config (run `oci setup config`); nothing secret is in this folder.
provider "oci" {
  config_file_profile = var.oci_profile
  region              = var.region
}
