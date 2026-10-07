# HireKit. Every command lives in a Makefile; this root one delegates to each
# app folder (ADR-0007). `make help` lists the targets.
SHELL := /bin/bash
.DEFAULT_GOAL := help
BACKEND := backend
WEB := web
REGISTRY_NAMESPACE ?= midhunmareedu
IMAGE_TAG ?= latest
VM_IP ?= $(shell terraform -chdir=deploy/oracle/terraform output -raw public_ip)

.PHONY: help vm-copy vm-up images images-build images-push dev-web build-web setup dev worker worker-live check check-file fix test test-integration record lint typecheck format format-check migrate migrate-verify migrate-down migrate-new seed eval eval-prompts vuln doctor db db-reset clean

help: ## List targets
	@$(MAKE) --no-print-directory -C $(BACKEND) help
	@grep -E '^(images|vm|dev-web|build-web)[a-z-]*:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

# The gate. CI runs exactly this. It writes ../.bearing/state/.check-passed on success.
check: ## The gate: every gate in backend/ and web/
	@$(MAKE) --no-print-directory -C $(BACKEND) check
	@$(MAKE) --no-print-directory -C $(WEB) check

# The Bearing edit hook passes FILE as a path; Python goes to the backend's linter, TypeScript and friends to web's, by absolute path.
check-file: ## Lint one edited file, FILE=path (the Bearing edit hook runs this)
	@[ -n "$(FILE)" ] || { echo "check-file: FILE is empty, nothing checked" >&2; exit 1; }; \
	[ -f "$(FILE)" ] || { echo "check-file: $(FILE) does not exist, nothing checked" >&2; exit 1; }; \
	case "$(FILE)" in \
	  *.ts|*.tsx|*.js) app=$(WEB);; \
	  *) app=$(BACKEND);; \
	esac; \
	$(MAKE) --no-print-directory -C $$app check-file FILE="$$(realpath "$(FILE)")"

# Targets both apps have run in backend/ then web/; the rest are backend-only (web has no database or model recording).
setup fix test lint typecheck format format-check vuln doctor clean:
	@$(MAKE) --no-print-directory -C $(BACKEND) $@
	@$(MAKE) --no-print-directory -C $(WEB) $@

dev-web: ## Run the web dev server (proxies /v1 to the API on :8080)
	@$(MAKE) --no-print-directory -C $(WEB) dev

build-web: ## Typecheck and build the web app into web/dist
	@$(MAKE) --no-print-directory -C $(WEB) build

dev worker worker-live test-integration record migrate migrate-verify migrate-down migrate-new seed eval eval-prompts db db-reset:
	@$(MAKE) --no-print-directory -C $(BACKEND) $@ $(if $(name),name=$(name),)

# Docker Hub images for the Oracle VM (deploy/oracle/README.md). Log in first: docker login -u $(REGISTRY_NAMESPACE)
images-build: ## Build the backend and web images (linux/amd64); tag latest, IMAGE_TAG= overrides
	@REGISTRY_NAMESPACE=$(REGISTRY_NAMESPACE) IMAGE_TAG=$(IMAGE_TAG) deploy/oracle/build-push.sh build

images-push: ## Send the images for IMAGE_TAG to Docker Hub (run images-build first)
	@REGISTRY_NAMESPACE=$(REGISTRY_NAMESPACE) IMAGE_TAG=$(IMAGE_TAG) deploy/oracle/build-push.sh push

images: ## Build both images and send them to Docker Hub
	@REGISTRY_NAMESPACE=$(REGISTRY_NAMESPACE) IMAGE_TAG=$(IMAGE_TAG) deploy/oracle/build-push.sh all

# The Oracle VM. VM_IP defaults to the Terraform output; override with VM_IP=1.2.3.4. Both targets
# use your ssh key and need deploy/oracle/.env filled in (copy .env.example, never commit it).
vm-copy: ## Copy docker-compose.yml and deploy/oracle/.env to the VM (~/hirekit)
	@[ -f deploy/oracle/.env ] || { echo "vm-copy: deploy/oracle/.env is missing; copy .env.example and fill it in" >&2; exit 1; }
	ssh ubuntu@$(VM_IP) 'mkdir -p hirekit'
	scp deploy/oracle/docker-compose.yml deploy/oracle/.env ubuntu@$(VM_IP):hirekit/
	ssh ubuntu@$(VM_IP) 'chmod 600 hirekit/.env'

vm-up: ## On the VM: pull the latest images and start or restart the stack (migrations run first)
	ssh ubuntu@$(VM_IP) 'cd hirekit && docker compose pull && docker compose up -d'
