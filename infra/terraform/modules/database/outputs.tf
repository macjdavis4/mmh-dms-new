locals {
  user     = digitalocean_database_user.app.name
  password = digitalocean_database_user.app.password
}

output "pooled_url" {
  description = "Web app connection (PgBouncer, transaction mode, private network)."
  value       = "postgres://${local.user}:${urlencode(local.password)}@${digitalocean_database_connection_pool.app.private_host}:${digitalocean_database_connection_pool.app.port}/${digitalocean_database_connection_pool.app.name}"
  sensitive   = true
}

output "direct_url" {
  description = "Direct connection for migrations, the worker and pg_dump."
  value       = "postgres://${local.user}:${urlencode(local.password)}@${digitalocean_database_cluster.pg.private_host}:${digitalocean_database_cluster.pg.port}/${digitalocean_database_db.app.name}"
  sensitive   = true
}

output "admin_url" {
  description = "Database owner (doadmin). Used only to run migrations; never given to the app."
  value       = "postgres://${digitalocean_database_cluster.pg.user}:${urlencode(digitalocean_database_cluster.pg.password)}@${digitalocean_database_cluster.pg.private_host}:${digitalocean_database_cluster.pg.port}/${digitalocean_database_db.app.name}"
  sensitive   = true
}

output "app_role" {
  value = digitalocean_database_user.app.name
}

output "ca_certificate" {
  value     = data.digitalocean_database_ca.pg.certificate
  sensitive = true
}

output "cluster_urn" {
  value = digitalocean_database_cluster.pg.urn
}

output "cluster_id" {
  value = digitalocean_database_cluster.pg.id
}
