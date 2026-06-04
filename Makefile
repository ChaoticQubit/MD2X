# md2x — convenience targets
#
#   make install            — run local-only installer (.venv + .tools/ + node_modules/)
#   make check              — show which binaries are resolved
#   make sample             — render examples/sample.md
#   make pdf IN=foo.md      — render an arbitrary file
#   make clean              — delete generated PDFs + intermediates
#   make distclean          — also remove .venv / .tools / node_modules

PY ?= python3
RUN := PYTHONPATH=src $(PY) -m md2x
SAMPLE := examples/sample.md
IN ?=

.PHONY: install check test sample pdf clean distclean help

help:
	@echo "Targets:"
	@echo "  install            Local install (no global pollution)"
	@echo "  check              Show resolved binary paths"
	@echo "  test               Run the pytest suite"
	@echo "  sample             Render examples/sample.md"
	@echo "  pdf IN=file.md     Render an arbitrary file"
	@echo "  clean              Delete generated PDFs + intermediate files"
	@echo "  distclean          Also wipe .venv / .tools / node_modules"

install:
	@chmod +x install.sh
	@./install.sh

check:
	@$(PY) _check.py

test:
	@.venv/bin/python -m pytest

sample: $(SAMPLE)
	@$(RUN) $(SAMPLE)

pdf:
	@if [ -z "$(IN)" ]; then echo "Usage: make pdf IN=path/to/file.md"; exit 1; fi
	@$(RUN) $(IN)

clean:
	@find . -name "*._md2x.md" -delete
	@find . -name "*._md2x.json" -delete
	@find examples -name "*.pdf" -delete 2>/dev/null || true
	@rm -rf examples/diagrams 2>/dev/null || true
	@echo "cleaned generated files"

distclean: clean
	@rm -rf .venv .tools .bin node_modules package-lock.json
	@echo "wiped local install"
