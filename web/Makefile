# HireKit web (React + Vite, run from web/; the root Makefile delegates here). Every command lives here. `make help` lists them.
SHELL := /bin/bash
.DEFAULT_GOAL := help
PNPM ?= pnpm
BIN := node_modules/.bin
STATE := ../.bearing/state
SKIPPED := $(STATE)/.skipped-web
# The gates `make check` runs, in order.
GATES := format-check lint typecheck test vuln
# Files each gate looks at: tracked plus untracked, minus ignored (so a fresh checkout counts).
SRC_FILES = $$(git ls-files -co --exclude-standard -- 'src/*.ts' 'src/*.tsx' '*.config.ts')
FMT_FILES = $$(git ls-files -co --exclude-standard -- '*.ts' '*.tsx' '*.js' '*.json' '*.css' '*.html' | grep -v '^pnpm-lock.yaml$$' || true)
TEST_FILES = $$(git ls-files -co --exclude-standard -- 'src/*.test.ts' 'src/*.test.tsx')

# $(call skip,gate,tool): the tool is absent. Print it, record it, and let the
# other gates run; `check` fails on any recorded skip. Never a silent pass.
define skip
{ mkdir -p $(STATE); echo "$(1): SKIPPED ($(2) not installed)"; echo "$(1) $(2)" >> $(SKIPPED); exit 0; }
endef

.PHONY: help setup dev build check check-file fix test lint typecheck format format-check vuln doctor clean

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

setup: ## Install dependencies from the lockfile (writes pnpm-lock.yaml when absent)
	@if [ -f pnpm-lock.yaml ]; then $(PNPM) install --frozen-lockfile; else echo "setup: no pnpm-lock.yaml yet, installing unfrozen; commit the lockfile it writes"; $(PNPM) install; fi
	@echo "setup done"

dev: ## Run the Vite dev server on :5173; /v1 is proxied to API_PROXY_TARGET (default http://localhost:8080)
	$(PNPM) exec vite --port 5173 --strictPort

build: ## Typecheck and build into dist/
	$(PNPM) run build
	@echo "build: $$(find dist -type f | wc -l | tr -d ' ') files in dist/"

format: ## Prettier --write
	@$(PNPM) exec prettier --log-level warn --write $(FMT_FILES)

format-check: ## Fail if any file is unformatted
	@files="$(FMT_FILES)"; n=$$(echo "$$files" | grep -c . || true); \
	[ "$$n" -gt 0 ] || { echo "format-check: 0 files, nothing checked" >&2; exit 1; }; \
	[ -x $(BIN)/prettier ] || $(call skip,format-check,prettier); \
	$(PNPM) exec prettier --log-level warn --check $$files || { echo "format-check: run make fix" >&2; exit 1; }; \
	echo "format-check: $$n files checked"

lint: ## ESLint with zero warnings allowed
	@n=$$(echo "$(SRC_FILES)" | grep -c . || true); \
	[ "$$n" -gt 0 ] || { echo "lint: 0 source files, nothing checked" >&2; exit 1; }; \
	[ -x $(BIN)/eslint ] || $(call skip,lint,eslint); \
	$(PNPM) exec eslint . --max-warnings 0 && echo "lint: $$n files checked"

typecheck: ## tsc --noEmit (strict)
	@n=$$(echo "$(SRC_FILES)" | grep -c . || true); \
	[ "$$n" -gt 0 ] || { echo "typecheck: 0 source files, nothing checked" >&2; exit 1; }; \
	[ -x $(BIN)/tsc ] || $(call skip,typecheck,tsc); \
	$(PNPM) exec tsc --noEmit -p tsconfig.json && echo "typecheck: $$n files checked"

test: ## Unit tests with an 80 percent coverage floor (vitest, jsdom, fetch stubbed)
	@n=$$(echo "$(TEST_FILES)" | grep -c . || true); \
	[ "$$n" -gt 0 ] || { echo "test: 0 test files, nothing checked" >&2; exit 1; }; \
	[ -x $(BIN)/vitest ] || $(call skip,test,vitest); \
	set -o pipefail; $(PNPM) exec vitest run --coverage 2>&1 | tail -60 && echo "test: $$n test files checked"

vuln: ## pnpm audit at high and above over the committed lockfile
	@command -v $(PNPM) >/dev/null || $(call skip,vuln,pnpm); \
	[ -f pnpm-lock.yaml ] || { echo "vuln: no pnpm-lock.yaml; run make setup and commit it" >&2; exit 1; }; \
	$(PNPM) audit --audit-level=high || exit 1; \
	n=$$($(PNPM) ls --depth 100 --parseable 2>/dev/null | grep -c node_modules || true); \
	[ "$$n" -gt 0 ] || { echo "vuln: 0 packages audited" >&2; exit 1; }; echo "vuln: $$n packages checked"

check: ## The gate: every gate in GATES, then the tally. CI runs exactly this.
	@mkdir -p $(STATE); rm -f $(SKIPPED) $(STATE)/.check-passed
	@for g in $(GATES); do $(MAKE) --no-print-directory $$g || { echo "check: $$g failed" >&2; exit 1; }; done
	@s=$$(cut -d' ' -f1 $(SKIPPED) 2>/dev/null | sort -u | wc -l | tr -d ' '); r=$$(( $(words $(GATES)) - s )); \
	echo "check: $$r gates run, $$s skipped"; \
	if [ "$$s" -eq 0 ]; then touch $(STATE)/.check-passed; echo "check: passed"; \
	elif [ "$${BEARING_ALLOW_SKIP:-0}" = "1" ] && [ -z "$$CI" ]; then sed 's/^/  skipped: /' $(SKIPPED); echo "check: passed with skips (BEARING_ALLOW_SKIP=1 is a local convenience; CI never sets it)"; \
	else sed 's/^/  skipped: /' $(SKIPPED); echo "check: FAILED, $$s gate(s) skipped; run make setup, or BEARING_ALLOW_SKIP=1 make check locally" >&2; exit 1; fi

check-file: ## Lint one edited file, FILE=path (the Bearing edit hook runs this)
	@[ -n "$(FILE)" ] || { echo "check-file: FILE is empty, nothing checked" >&2; exit 1; }; \
	[ -f "$(FILE)" ] || { echo "check-file: $(FILE) does not exist, nothing checked" >&2; exit 1; }; \
	case "$(FILE)" in \
	  *.ts|*.tsx|*.js) [ -x $(BIN)/eslint ] || { echo "check-file: eslint not installed (make setup), $(FILE) not checked"; exit 0; }; $(BIN)/eslint --max-warnings 0 "$(FILE)" || exit 1;; \
	  *) echo "check-file: no per-file check for $(FILE)"; exit 0;; \
	esac; \
	echo "check-file: 1 file checked"

fix: format ## Apply every automatic fix
	@$(PNPM) exec eslint . --fix || true

doctor: ## Environment diagnostics
	@echo "node:     $$(command -v node >/dev/null && node --version || echo missing)"
	@echo "pnpm:     $$(command -v $(PNPM) >/dev/null && $(PNPM) --version 2>/dev/null || echo missing)"
	@echo "deps:     $$([ -d node_modules ] && echo installed || echo 'NOT INSTALLED (run make setup)')"
	@echo "lockfile: $$([ -f pnpm-lock.yaml ] && echo present || echo 'MISSING (run make setup and commit pnpm-lock.yaml)')"
	@echo "tsc:      $$([ -x $(BIN)/tsc ] && $(BIN)/tsc --version || echo missing)"

clean: ## Remove build and test output
	rm -rf dist coverage $(STATE)/.check-passed $(SKIPPED)
