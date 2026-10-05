# DigitalOcean Managed PostgreSQL: daily backups and point-in-time recovery
# are built in. Only the app Droplet may connect; TLS is required.

terraform {
  required_providers {
    digitalocean = { source = "digitalocean/digitalocean" }
  }
}

resource "digitalocean_database_cluster" "pg" {
  name                 = "mmh-${var.environment}-pg"
  engine               = "pg"
  version              = "16"
  size                 = var.size
  region               = var.region
  node_count           = 1
  private_network_uuid = var.vpc_id
  tags                 = ["mmh", "mmh-${var.environment}"]

  maintenance_window {
    day  = "sunday"
    hour = "08:00:00" # UTC; 3-4 AM in Bangor
  }

  lifecycle {
    prevent_destroy = true # data must never be lost
  }
}

resource "digitalocean_database_db" "app" {
  cluster_id = digitalocean_database_cluster.pg.id
  name       = "mmh"
}

resource "digitalocean_database_user" "app" {
  cluster_id = digitalocean_database_cluster.pg.id
  name       = "mmh_app"
}

# PgBouncer in transaction mode for the web app.
resource "digitalocean_database_connection_pool" "app" {
  cluster_id = digitalocean_database_cluster.pg.id
  name       = "mmh-pool"
  mode       = "transaction"
  size       = var.pool_size
  db_name    = digitalocean_database_db.app.name
  user       = digitalocean_database_user.app.name
}

resource "digitalocean_database_firewall" "app" {
  cluster_id = digitalocean_database_cluster.pg.id
  rule {
    type  = "droplet"
    value = var.droplet_id
  }
}

data "digitalocean_database_ca" "pg" {
  cluster_id = digitalocean_database_cluster.pg.id
}
