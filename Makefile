SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
PYTHONPATH := src
export PYTHONPATH

.PHONY: help lint test test-browser check

help:
	@printf "Available targets:\n"
	@printf "  make lint   Compile Python source and tests\n"
	@printf "  make test   Run unit tests\n"
	@printf "  make test-browser  Run opt-in Playwright fake-AnkiWeb tests\n"
	@printf "  make check  Run lint and tests\n"

lint:
	@$(PYTHON) -m compileall -q src tests

test:
	@$(PYTHON) -m unittest discover -s tests -v

test-browser:
	@ANKI_ADDON_RELEASE_BROWSER_TESTS=1 $(PYTHON) -m unittest tests.test_browser_flows -v

check: lint test
