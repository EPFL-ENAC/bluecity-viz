NBS := $(sort $(wildcard notebooks/0*.py))

.PHONY: all sync edit run-all check export clean

all: check

sync:
	uv sync

# Open a notebook in the marimo editor: make edit NB=04  (default: first one)
NB ?= 01
edit:
	uv run marimo edit notebooks/$(NB)_*.py

# Execute every notebook top-to-bottom as a script (fails loudly on any error)
run-all:
	for nb in $(NBS); do \
		echo "=== $$nb ==="; \
		uv run python $$nb || exit 1; \
	done

# Validate marimo format / dataflow
check:
	uv run marimo check $(NBS)

# Client-facing deliverable: the executive summary as one self-contained HTML file
export:
	uv run marimo export html --no-include-code \
		notebooks/00_executive_summary.py -o outputs/executive_summary.html

clean:
	rm -rf outputs data/cache notebooks/__marimo__
