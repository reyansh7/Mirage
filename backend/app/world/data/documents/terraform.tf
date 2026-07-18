terraform {
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "build_server" {
  ami           = "ami-0abcdef1234567890"
  instance_type = "m5.large"
  tags = {
    Name = "build-server-01"
    Team = "DevOps"
  }
}
