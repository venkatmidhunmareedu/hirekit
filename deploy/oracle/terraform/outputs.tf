output "public_ip" {
  description = "Public IP of the VM. Use <ip>.sslip.io as SITE_ADDRESS if there is no domain."
  value       = oci_core_instance.this.public_ip
}

output "ssh" {
  description = "How to log in."
  value       = "ssh ubuntu@${oci_core_instance.this.public_ip}"
}
