terraform {
  required_providers {
    cloudflare = { source = "cloudflare/cloudflare" }
  }
}

# Proxied through Cloudflare (DDoS protection, WAF, hides the server's IP).
resource "cloudflare_dns_record" "app" {
  zone_id = var.zone_id
  name    = var.hostname
  type    = "A"
  content = var.ip_address
  proxied = true
  ttl     = 1 # automatic
  comment = "Maine Material Handling DMS (${var.environment}), managed by Terraform"
}

variable "zone_id" {
  type = string
}
variable "hostname" {
  type = string
}
variable "ip_address" {
  type = string
}
variable "environment" {
  type = string
}

output "fqdn" {
  value = var.hostname
}
