# Zone-level Cloudflare settings that apply only to the DMS hostnames, so
# other records in maine-material.com (website, email) are not affected.

terraform {
  required_version = ">= 1.9"
  required_providers {
    cloudflare = { source = "cloudflare/cloudflare", version = "~> 5.0" }
  }
  backend "s3" {
    bucket                      = "mmh-terraform-state"
    key                         = "shared/terraform.tfstate"
    region                      = "us-east-1"
    endpoints                   = { s3 = "https://nyc3.digitaloceanspaces.com" }
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
}

provider "cloudflare" {}

variable "cloudflare_zone_id" {
  type = string
}

variable "hostnames" {
  type    = list(string)
  default = ["dms.maine-material.com", "staging-dms.maine-material.com"]
}

# The only public addresses allowed to reach the DMS: the office, which is also
# where the VPN comes out. Same value as the SSH allow list (ADMIN_SSH_CIDRS).
variable "admin_ssh_cidrs" {
  type        = list(string)
  description = "Office public IP address(es), like [\"203.0.113.10/32\"]."

  validation {
    condition     = length(var.admin_ssh_cidrs) > 0
    error_message = "At least one office address is required, or everyone (including you) would be blocked."
  }
}

locals {
  host_expr = join(" or ", [for h in var.hostnames : "http.host eq \"${h}\""])
  # Cloudflare's rule language takes a bare address for a single host.
  office_expr = join(" ", [for c in var.admin_ssh_cidrs : replace(replace(c, "/32", ""), "/128", "")])
}

# Full (strict) TLS to the origin, always HTTPS, modern TLS only.
resource "cloudflare_ruleset" "dms_config" {
  zone_id     = var.cloudflare_zone_id
  name        = "DMS configuration"
  description = "TLS settings for the DMS hostnames (managed by Terraform)"
  kind        = "zone"
  phase       = "http_config_settings"
  rules = [{
    description = "Strict origin TLS for DMS"
    expression  = "(${local.host_expr})"
    action      = "set_config"
    action_parameters = {
      ssl                      = "strict"
      automatic_https_rewrites = true
    }
    enabled = true
  }]
}

# Don't let Cloudflare cache API answers or the app page.
resource "cloudflare_ruleset" "dms_cache" {
  zone_id     = var.cloudflare_zone_id
  name        = "DMS caching"
  description = "Bypass cache for the DMS except fingerprinted static files"
  kind        = "zone"
  phase       = "http_request_cache_settings"
  rules = [{
    description = "No caching outside /static/assets"
    expression  = "(${local.host_expr}) and not starts_with(http.request.uri.path, \"/static/assets/\")"
    action      = "set_cache_settings"
    action_parameters = {
      cache = false
    }
    enabled = true
  }]
}

# Network-only access: block every visitor whose address is not the office
# (or the VPN, which exits at the office). Only the health pages stay open so
# the deploy check and uptime monitors can see that the site is alive.
resource "cloudflare_ruleset" "dms_office_only" {
  zone_id     = var.cloudflare_zone_id
  name        = "DMS office-only access"
  description = "Only the office/VPN address may use the DMS (managed by Terraform)"
  kind        = "zone"
  phase       = "http_request_firewall_custom"
  rules = [{
    description = "Block everyone except the office, allowing /readyz and /healthz"
    expression  = "(${local.host_expr}) and not (ip.src in {${local.office_expr}}) and not (http.request.uri.path in {\"/readyz\" \"/healthz\"})"
    action      = "block"
    enabled     = true
  }]
}
