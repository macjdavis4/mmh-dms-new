output "droplet_id" {
  value = digitalocean_droplet.app.id
}
output "droplet_urn" {
  value = digitalocean_droplet.app.urn
}
output "public_ip" {
  value = digitalocean_reserved_ip.app.ip_address
}
output "firewall_id" {
  value = digitalocean_firewall.app.id
}
