# DigitalOcean Uptime on /readyz plus Droplet resource alerts, by email.
# (A second, independent monitor is set up by hand: docs/MANUAL_STEPS.md.)

terraform {
  required_providers {
    digitalocean = { source = "digitalocean/digitalocean" }
  }
}

resource "digitalocean_uptime_check" "readyz" {
  name    = "mmh-${var.environment}-readyz"
  target  = "https://${var.hostname}/readyz"
  type    = "https"
  regions = ["us_east", "us_west"]
  enabled = true
}

resource "digitalocean_uptime_alert" "down" {
  name       = "mmh-${var.environment}-down"
  check_id   = digitalocean_uptime_check.readyz.id
  type       = "down"
  period     = "2m"
  comparison = "less_than"
  threshold  = 1
  notifications {
    email = var.alert_emails
  }
}

resource "digitalocean_uptime_alert" "ssl" {
  name       = "mmh-${var.environment}-ssl-expiry"
  check_id   = digitalocean_uptime_check.readyz.id
  type       = "ssl_expiry"
  period     = "2m"
  comparison = "less_than"
  threshold  = 14
  notifications {
    email = var.alert_emails
  }
}

locals {
  droplet_alerts = {
    cpu    = { type = "v1/insights/droplet/cpu", value = 85, desc = "CPU above 85%" }
    memory = { type = "v1/insights/droplet/memory_utilization_percent", value = 90, desc = "Memory above 90%" }
    disk   = { type = "v1/insights/droplet/disk_utilization_percent", value = 80, desc = "Disk above 80%" }
  }
}

resource "digitalocean_monitor_alert" "droplet" {
  for_each = local.droplet_alerts
  alerts {
    email = var.alert_emails
  }
  window      = "10m"
  type        = each.value.type
  compare     = "GreaterThan"
  value       = each.value.value
  enabled     = true
  entities    = [var.droplet_id]
  description = "mmh-${var.environment}: ${each.value.desc}"
}

variable "environment" {
  type = string
}
variable "hostname" {
  type = string
}
variable "droplet_id" {
  type = string
}
variable "alert_emails" {
  type = list(string)
}
