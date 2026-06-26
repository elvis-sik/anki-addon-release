SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
PYTHONPATH := src
export PYTHONPATH

.PHONY: help lint test check

help:
	@printf "Available targets:\n"
	@printf "  make lint   Compile Python source and tests\n"
	@printf "  make test   Run unit tests\n"
	@printf "  make check  Run lint and tests\n"

lint:
	@$(PYTHON) -m compileall -q src tests

test:
	@$(PYTHON) -m unittest discover -s tests -v

check: lint test

