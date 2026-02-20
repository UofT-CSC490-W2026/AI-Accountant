variable "env" { type = string }
variable "db_password" { type = string; sensitive = true }
variable "db_address" { type = string }
variable "secret_name_prefix" { type = string }
