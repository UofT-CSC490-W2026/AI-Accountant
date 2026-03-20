variable "env" {
  type = string
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "db_instance_class" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "db_sg_id" {
  type = string
}

variable "restore_snapshot_id" {
  type    = string
  default = null
}
