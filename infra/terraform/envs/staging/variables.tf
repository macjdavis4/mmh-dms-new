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
  default = "10.30.0.0/20"
}
variable "droplet_size" {
  type    = string
  default = "s-1vcpu-2gb"
}
variable "droplet_backups" {
  type    = bool
  default = false
}
variable "database_size" {
  type    = string
  default = "db-s-1vcpu-1gb"
}
variable "database_pool_size" {
  type    = number
  default = 10
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
