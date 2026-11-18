### Defensive settings for make:
#     https://tech.davis-hansson.com/p/make/
SHELL:=bash
.ONESHELL:
.SHELLFLAGS:=-xeu -o pipefail -O inherit_errexit -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS+=--warn-undefined-variables
MAKEFLAGS+=--no-builtin-rules

# We like colors
# From: https://coderwall.com/p/izxssa/colored-makefile-for-golang-projects
RED=`tput setaf 1`
GREEN=`tput setaf 2`
RESET=`tput sgr0`
YELLOW=`tput setaf 3`

# Python checks
UV?=uv

# installed?
ifeq (, $(shell which $(UV) ))
  $(error "UV=$(UV) not found in $(PATH)")
endif

BACKEND_FOLDER=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

ifdef PLONE_VERSION
PLONE_VERSION := $(PLONE_VERSION)
else
PLONE_VERSION := 6.2.3
endif

ifdef CI
UV_VENV_ARGS :=
else
UV_VENV_ARGS := --python=3.12
endif

GIT_FOLDER=$(BACKEND_FOLDER)/.git
VENV_FOLDER=$(BACKEND_FOLDER)/.venv
export VIRTUAL_ENV=$(VENV_FOLDER)
BIN_FOLDER=$(VENV_FOLDER)/bin

# Tests and QA run through tox, configured by plone.meta
TOX=uvx --with tox-uv tox

# Environment variables to be exported
export PYTHONWARNINGS := ignore

all: install

# Add the following 'help' target to your Makefile
# And add help text after each target name starting with '\#\#'
.PHONY: help
help: ## This help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

requirements-mxdev.txt: pyproject.toml mx.ini ## Generate constraints file
	@echo "$(GREEN)==> Generate constraints file$(RESET)"
	@echo '-c https://dist.plone.org/release/$(PLONE_VERSION)/constraints.txt' > requirements.txt
	@uvx 'mxdev[uv]' -c mx.ini

$(VENV_FOLDER): requirements-mxdev.txt ## Install dependencies
	@echo "$(GREEN)==> Install environment$(RESET)"
	@if [[ -d "$(VENV_FOLDER)" ]]; then echo "$(YELLOW)==> Environment already exists at $(VENV_FOLDER)$(RESET)"; else uv venv $(UV_VENV_ARGS) $(VENV_FOLDER); fi
	@uv pip install -r requirements-mxdev.txt
	@uv pip install prek
	@if [[ -d "$(GIT_FOLDER)" ]]; then $(BIN_FOLDER)/prek install; else echo "$(RED)==> Not installing pre-commit hooks$(RESET)"; fi

.PHONY: sync
sync: $(VENV_FOLDER) ## Sync project dependencies
	@echo "$(GREEN)==> Sync project dependencies$(RESET)"
	@uv pip install -r requirements-mxdev.txt

instance/etc/zope.ini instance/etc/zope.conf: instance.yaml ## Create instance configuration
	@echo "$(GREEN)==> Create instance configuration$(RESET)"
	@uvx cookiecutter -f --no-input -c 3.1.0 --config-file instance.yaml gh:plone/cookiecutter-zope-instance

.PHONY: config
config: instance/etc/zope.ini

.PHONY: install
install: $(VENV_FOLDER) config ## Install Plone and dependencies

.PHONY: build
build: install ## Alias of install

.PHONY: clean
clean: ## Clean installation and instance (data left intact)
	@echo "$(RED)==> Cleaning environment and build$(RESET)"
	@rm -rf $(VENV_FOLDER) pyvenv.cfg .installed.cfg instance/etc .venv .pytest_cache .ruff_cache constraints* requirements*
	@rm -rf .tox build dist htmlcov .coverage coverage.xml src/*.egg-info

.PHONY: remove-data
remove-data: ## Remove all content
	@echo "$(RED)==> Removing all content$(RESET)"
	rm -rf $(VENV_FOLDER) instance/var

.PHONY: start
start: $(VENV_FOLDER) instance/etc/zope.ini ## Start a Plone instance on localhost:8080
	@$(BIN_FOLDER)/runwsgi instance/etc/zope.ini

.PHONY: console
console: $(VENV_FOLDER) instance/etc/zope.ini ## Start a console into a Plone instance
	@$(BIN_FOLDER)/zconsole debug instance/etc/zope.conf

.PHONY: create-site
create-site: $(VENV_FOLDER) instance/etc/zope.ini ## Create a new site from scratch
	@$(BIN_FOLDER)/zconsole run instance/etc/zope.conf ./scripts/create_site.py

# QA
.PHONY: lint
lint: ## Run pre-commit hooks (black, isort, flake8, zpretty, codespell...)
	@echo "$(GREEN)==> Lint codebase$(RESET)"
	@$(TOX) -e lint

.PHONY: format
format: ## Reformat code (pyupgrade, isort, black, zpretty)
	@echo "$(GREEN)==> Format codebase$(RESET)"
	@$(TOX) -e format

.PHONY: check
check: format lint ## Check and fix code base according to Plone standards

# i18n
$(BIN_FOLDER)/i18ndude: $(VENV_FOLDER)
	@echo "$(GREEN)==> Install translation tools$(RESET)"
	@uv pip install i18ndude

.PHONY: i18n
i18n: $(BIN_FOLDER)/i18ndude ## Update locales
	@echo "$(GREEN)==> Updating locales$(RESET)"
	@cd $(BACKEND_FOLDER)/src/collective/exportimport/locales && PATH=$(BIN_FOLDER):$$PATH ./update.sh

# Tests
.PHONY: test
test: ## Run tests with Plone 6.2.3
	@$(TOX) -e test

.PHONY: test-coverage
test-coverage: ## Run tests with coverage
	@$(TOX) -e coverage

.PHONY: test-all
test-all: ## Run lint, all supported Python / Plone versions and dependency checks
	@$(TOX)
