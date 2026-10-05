# Staging environment for the Maine Material Handling DMS.
# Same modules as the other environment; only sizes and names differ.

terraform {
  required_version = ">= 1.9"
  required_providers {
    digitalocean = { source = "digitalocean/digitalocean", version = "~> 2.70" }
    cloudflare   = { source = "cloudflare/cloudflare", version = "~> 5.0" }
  }

  # State lives in a Spaces bucket created by hand (docs/MANUAL_STEPS.md).
  # Credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY = a Spaces key.
  backend "s3" {
    bucket                      = "mmh-terraform-state"
    key                         = "staging/terraform.tfstate"
    region                      = "us-east-1"
    endpoints                   = { s3 = "https://nyc3.digitaloceanspaces.com" }
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
}

provider "digitalocean" {}
provider "cloudflare" {}

locals {
  environment = "staging"
  hostname    = "staging-dms.maine-material.com"
}

resource "digitalocean_vpc" "main" {
  name     = "mmh-${local.environment}"
  region   = var.region
  ip_range = var.vpc_cidr
}

module "app" {
  source                = "../../modules/app"
  environment           = local.environment
  region                = var.region
  vpc_id                = digitalocean_vpc.main.id
  droplet_size          = var.droplet_size
  droplet_backups       = var.droplet_backups
  admin_ssh_public_key  = var.admin_ssh_public_key
  deploy_ssh_public_key = var.deploy_ssh_public_key
  admin_ssh_cidrs       = var.admin_ssh_cidrs
  db_ca_certificate     = module.database.ca_certificate
}

module "database" {
  source      = "../../modules/database"
  environment = local.environment
  region      = var.region
  vpc_id      = digitalocean_vpc.main.id
  size        = var.database_size
  pool_size   = var.database_pool_size
  droplet_id  = module.app.droplet_id
}

module "storage" {
  source        = "../../modules/storage"
  environment   = local.environment
  region        = var.region
  backup_region = var.backup_region
  hostname      = local.hostname
}

module "dns" {
  source      = "../../modules/dns"
  zone_id     = var.cloudflare_zone_id
  hostname    = local.hostname
  ip_address  = module.app.public_ip
  environment = local.environment
}

module "monitoring" {
  source       = "../../modules/monitoring"
  environment  = local.environment
  hostname     = local.hostname
  droplet_id   = module.app.droplet_id
  alert_emails = var.alert_emails
}

resource "digitalocean_project" "mmh" {
  name        = "mmh-dms-${local.environment}"
  description = "Maine Material Handling DMS (${local.environment})"
  purpose     = "Web Application"
  environment = "Staging"
  resources = [
    module.app.droplet_urn,
    module.database.cluster_urn,
    module.storage.media_bucket_urn,
    module.storage.backup_bucket_urn,
  ]
}
