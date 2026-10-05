variable "environment" {
  type = string
}
variable "region" {
  type = string
}
variable "vpc_id" {
  type = string
}
variable "size" {
  type = string
}
variable "pool_size" {
  type    = number
  default = 20
}
variable "droplet_id" {
  type = string
}
