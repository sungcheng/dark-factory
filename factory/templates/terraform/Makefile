.PHONY: init plan apply destroy fmt validate lint clean

ENV ?= staging

init:				## Initialize Terraform
	terraform init

plan:				## Plan changes for an environment (usage: make plan ENV=staging)
	terraform plan -var-file=environments/$(ENV)/terraform.tfvars

apply:				## Apply changes for an environment (usage: make apply ENV=staging)
	terraform apply -var-file=environments/$(ENV)/terraform.tfvars

destroy:			## Destroy resources (usage: make destroy ENV=staging)
	terraform destroy -var-file=environments/$(ENV)/terraform.tfvars

fmt:				## Format all .tf files
	terraform fmt -recursive

validate:			## Validate Terraform configuration
	terraform validate

lint:				## Run tflint
	tflint --recursive

check:				## Format check + validate + lint
	terraform fmt -check -recursive
	terraform validate
	@which tflint > /dev/null 2>&1 && tflint --recursive || echo "tflint not installed — skipping"

clean:				## Remove Terraform cache
	rm -rf .terraform .terraform.lock.hcl

help:				## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
