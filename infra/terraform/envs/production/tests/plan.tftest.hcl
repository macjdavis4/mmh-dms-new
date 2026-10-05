# Plans the whole environment against mocked providers: catches broken
# templates, wiring and variable mistakes in CI without cloud credentials.
#   terraform init -backend=false && terraform test

mock_provider "digitalocean" {
  mock_data "digitalocean_database_ca" {
    defaults = { certificate = "-----BEGIN CERTIFICATE-----\nMOCK\n-----END CERTIFICATE-----" }
  }
}

mock_provider "cloudflare" {
  mock_data "cloudflare_ip_ranges" {
    defaults = {
      ipv4_cidrs = ["173.245.48.0/20"]
      ipv6_cidrs = ["2400:cb00::/32"]
    }
  }
}

variables {
  admin_ssh_public_key  = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockOwnerKey owner@office"
  deploy_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockDeployKey deploy"
  admin_ssh_cidrs       = ["203.0.113.10/32"]
  cloudflare_zone_id    = "0123456789abcdef0123456789abcdef"
  alert_emails          = ["owner@example.com"]
}

run "plan_production" {
  command = plan

  assert {
    condition     = module.dns.fqdn == "dms.maine-material.com"
    error_message = "Production must serve dms.maine-material.com"
  }
  assert {
    condition     = var.droplet_backups == true
    error_message = "Production Droplet backups must be on"
  }
  assert {
    condition     = var.region != var.backup_region
    error_message = "Backups must live in a different region"
  }
}
