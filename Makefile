# HireKit. Every command lives in a Makefile; this root one delegates to each
# app folder (ADR-0007). `make help` lists the targets.
SHELL := /bin/bash
.DEFAULT_GOAL := help
BACKEND := backend
WEB := web

.PHONY: help dev-web build-web setup dev check check-file fix test test-integration record lint typecheck format format-check migrate migrate-verify migrate-down migrate-new vuln doctor db db-reset clean

help: ## List targets
	@$(MAKE) --no-print-directory -C $(BACKEND) help

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

dev test-integration record migrate migrate-verify migrate-down migrate-new db db-reset:
	@$(MAKE) --no-print-directory -C $(BACKEND) $@ $(if $(name),name=$(name),)
