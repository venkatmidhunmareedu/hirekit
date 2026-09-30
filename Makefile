# HireKit. Every command lives in a Makefile; this root one delegates to each
# app folder (ADR-0007). `make help` lists the targets. web/ is added later.
SHELL := /bin/bash
.DEFAULT_GOAL := help
BACKEND := backend

.PHONY: help setup dev check check-file fix test test-integration lint typecheck format format-check migrate migrate-verify migrate-down migrate-new vuln doctor db db-reset clean

help: ## List targets
	@$(MAKE) --no-print-directory -C $(BACKEND) help

# The gate. CI runs exactly this. It writes ../.bearing/state/.check-passed on success.
check: ## The gate: every gate in backend/ (web/ joins when it exists)
	@$(MAKE) --no-print-directory -C $(BACKEND) check

# The Bearing edit hook passes FILE as a path; a Python file goes to the backend's linter by absolute path.
check-file: ## Lint one edited file, FILE=path (the Bearing edit hook runs this)
	@[ -n "$(FILE)" ] || { echo "check-file: FILE is empty, nothing checked" >&2; exit 1; }; \
	[ -f "$(FILE)" ] || { echo "check-file: $(FILE) does not exist, nothing checked" >&2; exit 1; }; \
	$(MAKE) --no-print-directory -C $(BACKEND) check-file FILE="$$(realpath "$(FILE)")"

setup dev fix test test-integration lint typecheck format format-check migrate migrate-verify migrate-down migrate-new vuln doctor db db-reset clean:
	@$(MAKE) --no-print-directory -C $(BACKEND) $@ $(if $(name),name=$(name),)
