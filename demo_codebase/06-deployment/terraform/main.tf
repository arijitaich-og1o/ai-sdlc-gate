provider "aws" {
  region = "ap-south-1"
}

resource "aws_s3_bucket" "exports" {
  bucket = "og1o-customer-exports"
  acl    = "public-read"
}

resource "aws_security_group" "db" {
  name = "accounts-db"

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_instance" "accounts" {
  identifier             = "accounts-prod"
  engine                 = "postgres"
  instance_class         = "db.t3.medium"
  allocated_storage      = 100
  username               = "accounts"
  password               = "Sup3rS3cretPr0d!"
  storage_encrypted      = false
  skip_final_snapshot    = true
  backup_retention_period = 0
  publicly_accessible    = true
  vpc_security_group_ids = [aws_security_group.db.id]
}

resource "aws_iam_policy" "deployer" {
  name   = "accounts-deployer"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}
