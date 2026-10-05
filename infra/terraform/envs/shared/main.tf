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

locals {
  host_expr = join(" or ", [for h in var.hostnames : "http.host eq \"${h}\""])
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
