variable "region" {
  type    = string
  default = "nyc3"
}
variable "backup_region" {
  type    = string
  default = "sfo3"
}
variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/20"
}
variable "droplet_size" {
  type    = string
  default = "s-2vcpu-4gb"
}
variable "droplet_backups" {
  type    = bool
  default = true
}
variable "database_size" {
  type    = string
  default = "db-s-1vcpu-2gb"
}
variable "database_pool_size" {
  type    = number
  default = 20
}
variable "admin_ssh_public_key" {
  type = string
}
variable "deploy_ssh_public_key" {
  type = string
}
variable "admin_ssh_cidrs" {
  type = list(string)
}
variable "cloudflare_zone_id" {
  type = string
}
variable "alert_emails" {
  type = list(string)
}
