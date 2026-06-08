# md2x — convenience targets
#
# Setup / housekeeping
#   make install                 — local-only installer (.venv + .tools/ + node_modules/)
#   make check                   — show which binaries are resolved
#   make test                    — run the pytest suite
#   make clean / distclean       — remove generated files / wipe local install
#
# AI site — config-driven (edit md2x.yaml, then just):
#   make start                   — build the site (site.input → site.output)
#   make serve                   — preview the built site at http://localhost:8000
#
# Publish to PyPI:
#   make build                   — sdist + wheel into dist/
#   make publish                 — upload dist/* (bump version in pyproject first)
#
# Convert one Markdown file (pdf | docx | html | epub | latex)
#   make docx IN=foo.md                  — output alongside input (foo.docx)
#   make docx foo.md                     — positional form (same thing)
#   make docx IN=foo.md OUT=out/bar.docx — choose the output path
#
# Build a website from files/dirs (site = no AI; ai-site = agno; deploy = + Vercel)
#   make site IN="docs/ intro.md"        — deterministic, no LLM/network → ./site
#   make ai-site docs/ OUT=public        — AI-generated → ./public
#   make deploy IN=docs/                 — AI site then push to Vercel (needs VERCEL_TOKEN)
#
# IN= (or a positional path) is the input; OUT= is the output file (convert) or
# directory (site). For site targets IN may list several files/dirs.

PY      ?= python3
VENV_PY := .venv/bin/python
# Prefer the local venv python (it has pyyaml + agno + provider SDKs) when present,
# so `make ai-site` works after `pip install md2x[ai]`; fall back to system python.
PYBIN   := $(if $(wildcard $(VENV_PY)),$(VENV_PY),$(PY))
RUN     := PYTHONPATH=src $(PYBIN) -m md2x
CFG     ?= md2x.yaml

IN  ?=
OUT ?=

# Every real target — used to separate them from positional file/dir args.
KNOWN := install check test help start serve build publish release \
         pdf docx html epub latex site ai-site deploy clean distclean
# Goals that are not real targets are treated as positional input paths.
ARGS  := $(filter-out $(KNOWN),$(MAKECMDGOALS))
# IN= wins; otherwise use the positional path(s).
INPUT := $(if $(IN),$(IN),$(ARGS))
# -o flag, only when OUT is set (quoted to tolerate spaces).
OUTFLAG = $(if $(OUT),-o "$(OUT)")

.PHONY: install check test help start serve build publish release \
        pdf docx html epub latex site ai-site deploy clean distclean

help:
	@echo "Setup:"
	@echo "  install                         Local install (no global pollution)"
	@echo "  check                           Show resolved binary paths"
	@echo "  test                            Run the pytest suite"
	@echo ""
	@echo "AI site (edit md2x.yaml, then):"
	@echo "  start                           Build site.input -> site.output"
	@echo "  serve                           Preview at http://localhost:8000"
	@echo ""
	@echo "Convert (pdf docx html epub latex):"
	@echo "  make docx IN=file.md            Output alongside input"
	@echo "  make docx file.md               Positional form"
	@echo "  make docx IN=file.md OUT=o.docx Choose the output path"
	@echo ""
	@echo "Website:"
	@echo "  make site IN=\"docs/ a.md\"       Deterministic site (no AI) -> ./site"
	@echo "  make ai-site docs/ OUT=public   AI site (agno) -> ./public"
	@echo "  make deploy IN=docs/            AI site + deploy to Vercel (VERCEL_TOKEN)"
	@echo ""
	@echo "Publish to PyPI:"
	@echo "  build                           Build sdist + wheel into dist/"
	@echo "  publish                         Upload dist/* to PyPI"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean                           Delete generated outputs + intermediates"
	@echo "  distclean                       Also wipe .venv / .tools / node_modules"

install:
	@chmod +x install.sh
	@./install.sh

check:
	@$(RUN) --check

test:
	@$(PYBIN) -m pytest

# --- AI site: config-driven (input/output come from md2x.yaml) --------------
# read site.<key> from the YAML config with a fallback (pyyaml ships in .venv).
cfgval = $(shell $(PYBIN) -c "import yaml;c=yaml.safe_load(open('$(CFG)'))or{};print((c.get('site') or {}).get('$(1)') or '$(2)')" 2>/dev/null)

start:
	@test -f $(CFG) || { echo "no $(CFG) — run 'make install' (it copies md2x.example.yaml)"; exit 1; }
	@in="$(call cfgval,input,.)"; out="$(call cfgval,output,site)"; \
	 echo "building site from '$$in' -> '$$out'  (config: $(CFG))"; \
	 $(RUN) site $$in -o "$$out" && \
	 echo "" && echo "done — preview with 'make serve' (or open $$out/index.html)"

serve:
	@out="$(call cfgval,output,site)"; \
	 test -d "$$out" || { echo "no site at '$$out' — run 'make start' first"; exit 1; }; \
	 echo "serving '$$out' at http://localhost:8000  (Ctrl-C to stop)"; \
	 cd "$$out" && $(PYBIN) -m http.server 8000

# --- packaging / PyPI -------------------------------------------------------
build:
	@$(PYBIN) -m pip install -q build
	@rm -rf dist
	@$(PYBIN) -m build
	@echo "built: $$(ls dist/ 2>/dev/null | tr '\n' ' ')"

publish: build
	@$(PYBIN) -m pip install -q twine
	@echo "uploading dist/* to PyPI (needs a PyPI token or ~/.pypirc — see README)"
	@$(PYBIN) -m twine upload dist/*

release: publish
	@echo "published. Tag it so the GitHub Action matches on the next Release:"
	@echo "  git tag v<version> && git push origin v<version>"

# --- convert: format == target name ($@) ------------------------------------
pdf docx html epub latex:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make $@ IN=file.md [OUT=out.$@]   (or: make $@ file.md)"; \
		exit 1; \
	fi
	@$(RUN) $(INPUT) $(OUTFLAG) --to $@

# --- website ----------------------------------------------------------------
site:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make site IN=\"docs/ file.md\" [OUT=dir]   (or: make site docs/)"; \
		exit 1; \
	fi
	@$(RUN) site $(INPUT) $(OUTFLAG) --no-ai

ai-site:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make ai-site IN=docs/ [OUT=dir]   (or: make ai-site docs/)"; \
		exit 1; \
	fi
	@$(RUN) site $(INPUT) $(OUTFLAG)

deploy:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make deploy IN=docs/ [OUT=dir]   (needs VERCEL_TOKEN)"; \
		exit 1; \
	fi
	@$(RUN) site $(INPUT) $(OUTFLAG) --deploy vercel

clean:
	@find . -name "*._md2x.md" -delete
	@find . -name "*._md2x.json" -delete
	@find examples \( -name "*.pdf" -o -name "*.docx" -o -name "*.html" \
		-o -name "*.epub" -o -name "*.tex" \) -delete 2>/dev/null || true
	@rm -rf examples/diagrams site 2>/dev/null || true
	@echo "cleaned generated files"

distclean: clean
	@rm -rf .venv .tools .bin node_modules package-lock.json
	@echo "wiped local install"

# Keep Make from trying to (re)build the Makefile via the catch-all below.
Makefile: ;

# Positional input support: any extra command-line goal that is not a real
# target (e.g. `make docx file.md`) is a file/dir path — match it with a no-op
# so Make doesn't error "no rule to make target". Real targets above win.
# Caveat: a mistyped target name is silently treated as a no-op path.
%:
	@:
