# Spaces buckets:
#  - media (primary region, versioned): photos, scanned cards, invoices
#  - backups (second region, versioned): nightly encrypted pg_dumps and a
#    nightly copy of media. Dumps expire after 30 days.

terraform {
  required_providers {
    digitalocean = { source = "digitalocean/digitalocean" }
  }
}

resource "digitalocean_spaces_bucket" "media" {
  name   = "mmh-${var.environment}-media"
  region = var.region
  acl    = "private"

  versioning {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Lets the browser upload photos and scans straight to Spaces (Phase 2).
resource "digitalocean_spaces_bucket_cors_configuration" "media" {
  bucket = digitalocean_spaces_bucket.media.id
  region = var.region
  cors_rule {
    allowed_methods = ["GET", "PUT"]
    allowed_origins = ["https://${var.hostname}"]
    allowed_headers = ["*"]
    max_age_seconds = 3600
  }
}

resource "digitalocean_spaces_bucket" "backups" {
  name   = "mmh-${var.environment}-backups"
  region = var.backup_region
  acl    = "private"

  # Versioning keeps overwritten or deleted backups recoverable for 30 days,
  # even if the app's key were misused.
  versioning {
    enabled = true
  }

  lifecycle_rule {
    id      = "expire-db-dumps"
    enabled = true
    prefix  = "db/"
    expiration {
      days = var.backup_retention_days
    }
    noncurrent_version_expiration {
      days = var.backup_retention_days
    }
  }

  lifecycle_rule {
    id      = "expire-old-media-versions"
    enabled = true
    prefix  = "media/"
    noncurrent_version_expiration {
      days = 90
    }
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Key used by the app: read/write on media, write backups.
resource "digitalocean_spaces_key" "app" {
  name = "mmh-${var.environment}-app"
  grant {
    bucket     = digitalocean_spaces_bucket.media.name
    permission = "readwrite"
  }
  grant {
    bucket     = digitalocean_spaces_bucket.backups.name
    permission = "readwrite"
  }
}
