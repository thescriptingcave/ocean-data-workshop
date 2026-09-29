# Ocean data workshop
#
# Every task works the same on macOS (Apple silicon), Linux and Windows, because it
# goes through `uv run` and a Python script rather than a shell script. `make` itself
# is the one thing to install.
#
#   make            setup + open Jupyter Lab
#   make setup      one-command environment setup
#   make lab        open Jupyter Lab (the usual way to work)
#   make notebook   run every notebook top to bottom, with output saved
#   make test       notebooks, unit tests, lint
#   make check      the offline guarantee: everything with the network forbidden
#   make fresh      clean clone test -- proves setup works from nothing
#   make clean      remove generated notebooks and scratch files
#
# Override the database port if you already run PostgreSQL locally:
#   make setup PORT=5433

PORT      ?= 5432
export OCEAN_DATA_WORKSHOP_PORT = $(PORT)

UV        ?= uv
UVRUN     ?= $(UV) run
PY        := $(shell $(UV) run python -c "import sys; print(sys.executable)" 2>/dev/null)
NB_DIR    := notebooks
PORT_ARGS := $(if $(filter 5432,$(PORT)),,--port $(PORT))

.DEFAULT_GOAL := all
.PHONY: all setup lab lab-offline notebook notebooks test check check-notebooks check-independence \
        lint unit fresh clean clean-cache help deps kernel prefetch db db-ocean shell \
        beginners

## all: set up, then open Jupyter Lab
all: setup lab

## setup: install deps, start the database, load the data, warm the API cache
setup:
	@$(UVRUN) workshop-setup $(PORT_ARGS)

## deps: sync Python dependencies only
deps:
	@$(UV) sync

## kernel: register the Jupyter kernel (setup does this too)
kernel:
	@$(UVRUN) python -m ipykernel install --user --name python3 \
		--display-name "Python 3 (ocean-sim)"

## lab: open Jupyter Lab on the notebooks
lab: kernel
	@$(UVRUN) jupyter lab $(NB_DIR)/

## lab-offline: open Jupyter Lab with the network forbidden
##
## The network-is-bad case is also one command. Everything is served from the cache, and
## each request prints a warning saying so -- the numbers are real, just not new.
lab-offline: kernel
	@OCEAN_DATA_WORKSHOP_OFFLINE=1 $(UVRUN) jupyter lab $(NB_DIR)/

## beginners: rebuild and run the beginners tier (5 notebooks, no database)
##
## Separate from `make notebook` on purpose. The beginners tier assumes no API
## experience and has no dependency on the database, the cache or the Makefile --
## it is the thing to give someone who has never fetched a URL.
beginners:
	@$(UV) run --with duckdb python scripts/build_beginners.py --execute

## notebook: execute every notebook, saving output -- the supported way to run them
notebook:
	@$(UVRUN) python scripts/build_notebooks.py --execute

## notebooks: rebuild the .ipynb files from their Python definitions
notebooks:
	@$(UVRUN) python scripts/build_notebooks.py

## prefetch: warm the API cache so the notebooks need no network
prefetch:
	@$(UVRUN) python scripts/prefetch.py

## db: apply the schema and load the data (the fast three)
db:
	@$(UVRUN) python scripts/load_db.py

## db-ocean: also load the GLORYS ocean profile -- ~325 MB of transfer
##
## Deliberately separate. It is the slowest thing in setup by an order of magnitude,
## it needs a Copernicus account, and only notebook 08 touches it. The workshop's
## result -- wind against underwater noise -- needs only wind and acoustics.
db-ocean:
	@$(UVRUN) python scripts/load_db.py --with-ocean

## test: everything -- notebooks, independence, unit tests, lint
test: check-notebooks check-independence unit lint

## check-notebooks: execute all notebooks and fail on any unhandled error
check-notebooks:
	@$(UVRUN) python scripts/build_notebooks.py --execute

## check-independence: report cells that cannot be run on their own
##
## A report, not a gate. The notebooks are sequential teaching material, so some cells
## legitimately build on the cell above. What this catches is the real bug class: a
## cell missing an import, or a variable defined eight cells earlier and used one cell
## later, which passes "Run All" and fails the moment somebody jumps in.
check-independence:
	@$(UVRUN) python scripts/check_cell_independence.py || true

## unit: run the unit tests
unit:
	@$(UVRUN) pytest -q

## lint: check the Python
lint:
	@$(UVRUN) ruff check src/ scripts/

## check: the offline guarantee -- every notebook with the network forbidden
##
## The cache exists so a bad venue network cannot end the session. This is the test
## that actually proves it, and it is a different test from `make test`: it forces the
## failure path that a healthy network never exercises.
check:
	@echo "  --- notebooks, network FORBIDDEN ---"
	@OCEAN_DATA_WORKSHOP_OFFLINE=1 $(UVRUN) python scripts/build_notebooks.py --execute
	@echo "  --- prefetch from cache only ---"
	@OCEAN_DATA_WORKSHOP_OFFLINE=1 $(UVRUN) python scripts/prefetch.py

## fresh: clone to a temp directory and run setup from nothing
##
## The only test that catches "works on my machine". Found the .gitignore bug that
## had excluded three source files from every commit, and a compose file that could
## not be started twice.
fresh:
	@rm -rf .fresh-clone
	@git clone -q . .fresh-clone
	@echo "  cloned to .fresh-clone -- no data/, no cache, no .env"
	@cd .fresh-clone && $(UVRUN) workshop-setup $(PORT_ARGS)
	@echo
	@echo "  now run:  cd .fresh-clone && make lab"
	@rm -rf .fresh-clone

## clean: remove generated notebooks and scratch files
clean:
	@rm -f $(NB_DIR)/*.ipynb
	@rm -f $(NB_DIR)/_*.nc $(NB_DIR)/_traps.csv
	@echo "  removed the generated notebooks -- 'make notebooks' puts them back"

## clean-cache: drop the prefetched responses, forcing a live fetch next time
clean-cache:
	@rm -rf $(NB_DIR)/.cache
	@echo "  cache cleared"

## shell: a Python shell with everything already imported
shell:
	@$(UVRUN) python

## help: list the targets
help:
	@grep -E '^## [a-z-]+:' $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
