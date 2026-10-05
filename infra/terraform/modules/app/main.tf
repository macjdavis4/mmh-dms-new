# One Droplet running Docker Compose (Caddy + blue/green app + worker).
# The Droplet holds no data: it can be destroyed and rebuilt from this module
# and the latest image in under an hour (see docs/RUNBOOK.md).

terraform {
  required_providers {
    digitalocean = { source = "digitalocean/digitalocean" }
    cloudflare   = { source = "cloudflare/cloudflare" }
  }
}

data "cloudflare_ip_ranges" "cf" {}

resource "digitalocean_ssh_key" "admin" {
  name       = "mmh-${var.environment}-admin"
  public_key = var.admin_ssh_public_key
}

resource "digitalocean_droplet" "app" {
  name       = "mmh-${var.environment}-app"
  image      = "ubuntu-24-04-x64"
  size       = var.droplet_size
  region     = var.region
  vpc_uuid   = var.vpc_id
  ipv6       = true
  monitoring = true
  backups    = var.droplet_backups
  ssh_keys   = [digitalocean_ssh_key.admin.fingerprint]
  tags       = ["mmh", "mmh-${var.environment}"]

  dynamic "backup_policy" {
    for_each = var.droplet_backups ? [1] : []
    content {
      plan = "daily"
      hour = 8 # UTC; 3-4 AM in Bangor
    }
  }

  user_data = templatefile("${path.module}/../../../cloud-init/droplet.yaml", {
    environment           = var.environment
    admin_username        = var.admin_username
    admin_ssh_public_key  = var.admin_ssh_public_key
    deploy_ssh_public_key = var.deploy_ssh_public_key
    deploy_entry_b64      = base64encode(file("${path.module}/../../../cloud-init/deploy-entry.sh"))
    db_ca_cert_b64        = base64encode(var.db_ca_certificate)
  })

  lifecycle {
    # Changing cloud-init or the base image would rebuild the server. Rebuilds
    # are done on purpose (terraform apply -replace=...), never by accident.
    ignore_changes = [user_data, image, ssh_keys]
  }
}

# A fixed public IP, so a rebuilt Droplet keeps the same DNS record.
resource "digitalocean_reserved_ip" "app" {
  region = var.region
}

resource "digitalocean_reserved_ip_assignment" "app" {
  ip_address = digitalocean_reserved_ip.app.ip_address
  droplet_id = digitalocean_droplet.app.id
}

resource "digitalocean_firewall" "app" {
  name        = "mmh-${var.environment}-app"
  droplet_ids = [digitalocean_droplet.app.id]

  # Web traffic only from Cloudflare's proxies.
  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = concat(data.cloudflare_ip_ranges.cf.ipv4_cidrs, data.cloudflare_ip_ranges.cf.ipv6_cidrs)
  }
  inbound_rule {
    protocol         = "udp"
    port_range       = "443"
    source_addresses = concat(data.cloudflare_ip_ranges.cf.ipv4_cidrs, data.cloudflare_ip_ranges.cf.ipv6_cidrs)
  }
  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = concat(data.cloudflare_ip_ranges.cf.ipv4_cidrs, data.cloudflare_ip_ranges.cf.ipv6_cidrs)
  }
  # SSH only from the office IP(s). GitHub Actions adds its own address for
  # the few minutes a deploy runs, then removes it.
  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = var.admin_ssh_cidrs
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  # Deploy jobs add a temporary SSH rule for their runner and always remove
  # it. Terraform runs share the deploy concurrency group, so they never
  # overlap with a deploy.
}
