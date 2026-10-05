output "media_bucket" {
  value = digitalocean_spaces_bucket.media.name
}
output "media_endpoint" {
  value = "https://${var.region}.digitaloceanspaces.com"
}
output "backup_bucket" {
  value = digitalocean_spaces_bucket.backups.name
}
output "backup_endpoint" {
  value = "https://${var.backup_region}.digitaloceanspaces.com"
}
output "app_key_id" {
  value = digitalocean_spaces_key.app.access_key
}
output "app_key_secret" {
  value     = digitalocean_spaces_key.app.secret_key
  sensitive = true
}
output "media_bucket_urn" {
  value = digitalocean_spaces_bucket.media.urn
}
output "backup_bucket_urn" {
  value = digitalocean_spaces_bucket.backups.urn
}
