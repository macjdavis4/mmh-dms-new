variable "environment" {
  type = string
}
variable "region" {
  type = string
}
variable "vpc_id" {
  type = string
}
variable "droplet_size" {
  type = string
}
variable "droplet_backups" {
  type    = bool
  default = true
}
variable "admin_username" {
  type    = string
  default = "mmhadmin"
}
variable "admin_ssh_public_key" {
  type        = string
  description = "Owner's SSH public key (for emergency access from the office)."
}
variable "deploy_ssh_public_key" {
  type        = string
  description = "Public half of the GitHub Actions deploy key. Can only run the deploy script."
}
variable "admin_ssh_cidrs" {
  type        = list(string)
  description = "IP ranges allowed to SSH in, e.g. [\"203.0.113.10/32\"]."
}
variable "db_ca_certificate" {
  type      = string
  sensitive = true
}
