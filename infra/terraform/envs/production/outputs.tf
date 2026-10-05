# Read by the deploy workflow (terraform output -json) to build the app's
# environment. Sensitive values never appear in logs.
output "hostname" {
  value = local.hostname
}
output "droplet_ip" {
  value = module.app.public_ip
}
output "firewall_id" {
  value = module.app.firewall_id
}
output "database_pooled_url" {
  value     = module.database.pooled_url
  sensitive = true
}
output "database_direct_url" {
  value     = module.database.direct_url
  sensitive = true
}
output "media_bucket" {
  value = module.storage.media_bucket
}
output "media_endpoint" {
  value = module.storage.media_endpoint
}
output "backup_bucket" {
  value = module.storage.backup_bucket
}
output "backup_endpoint" {
  value = module.storage.backup_endpoint
}
output "spaces_app_key_id" {
  value = module.storage.app_key_id
}
output "spaces_app_key_secret" {
  value     = module.storage.app_key_secret
  sensitive = true
}
