# Uncomment and configure for remote state
# terraform {
#   backend "s3" {
#     bucket         = "{{PROJECT_NAME}}-tfstate"
#     key            = "terraform.tfstate"
#     region         = "us-east-1"
#     dynamodb_table = "{{PROJECT_NAME}}-tflock"
#     encrypt        = true
#   }
# }
