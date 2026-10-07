data "oci_identity_availability_domains" "this" {
  compartment_id = var.compartment_ocid
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = "VM.Standard.A1.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_ocid
  display_name   = "hirekit"
  cidr_blocks    = ["10.0.0.0/16"]
}

resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "hirekit"
}

resource "oci_core_route_table" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "hirekit"
  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }
}

resource "oci_core_security_list" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "hirekit"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    description = "SSH from the engineer only"
    source      = var.ssh_allowed_cidr
    protocol    = "6"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Public web: Caddy serves the site and redirects 80 to 443.
  dynamic "ingress_security_rules" {
    for_each = [80, 443]
    content {
      description = "Public web"
      source      = "0.0.0.0/0"
      protocol    = "6"
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }
}

resource "oci_core_subnet" "this" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.this.id
  display_name      = "hirekit"
  cidr_block        = "10.0.0.0/24"
  route_table_id    = oci_core_route_table.this.id
  security_list_ids = [oci_core_security_list.this.id]
}

resource "oci_core_instance" "this" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.this.availability_domains[var.availability_domain_index].name
  display_name        = "hirekit"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_gb
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.this.id
    assign_public_ip = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }

  lifecycle {
    # A newer Ubuntu image must not replace the machine (and its database volume) on the next plan.
    ignore_changes = [source_details[0].source_id, metadata["user_data"]]
  }
}
