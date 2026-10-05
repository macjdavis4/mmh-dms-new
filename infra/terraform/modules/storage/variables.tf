variable "environment" {
  type = string
}
variable "region" {
  type = string
}
variable "backup_region" {
  type        = string
  description = "A different region from `region`, so one outage can't take both copies."
}
variable "hostname" {
  type = string
}
variable "backup_retention_days" {
  type    = number
  default = 30
}
