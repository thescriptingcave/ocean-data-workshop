# Ocean data workshop
#
# Every task works the same on macOS (Apple silicon), Linux and Windows, because it
# goes through `uv run` and a Python script rather than a shell script. `make` itself
# is the one thing to install.
#
#   make lab        setup (database, data, cache, Jupyter) then open Jupyter Lab
#   make setup      one-command environment setup (database, data, cache)
#   make notebook   run every notebook top to bottom, with output saved
#   make test       notebooks, unit tests, lint
#   make check      the offline guarantee: everything with the network forbidden
#   make fresh      clean clone test -- proves setup works from nothing
#   make clean      remove generated notebooks and scratch files
#   make clean-scratch  remove only cell-written scratch, keep the committed notebooks
#   make bonus      optional extras (PyTorch, for notebook 10 only)
#
# Override the database port if you already run PostgreSQL locally:
#   make setup PORT=5433

PORT      ?= 5432
export OCEAN_DATA_WORKSHOP_PORT = $(PORT)

UV        ?= uv
UVRUN     ?= $(UV) run
PY        := $(shell $(UV) run python -c "import sys; print(sys.executable)" 2>/dev/null)
# Every directory a build script writes notebooks into. `make clean` has to span all
# three: workshop_1 from build_beginners.py, workshop_2 and workshop_3 from
# build_notebooks.py. Naming only workshop_2 left the ML notebooks uncleanable, which is
# how a second full set of them survived a clean.
#
# Space-separated, and globbed per-directory with $(foreach) rather than by appending a
# glob onto the list. `$(NB_DIRS)/*.ipynb` would expand to
# `rm -f Workshop/workshop_1 Workshop/workshop_2 Workshop/workshop_3/*.ipynb`, where the
# first two become bare arguments and rm fails with "is a directory". (Colon separators
# do not help: they are only special in prerequisite lists, not in recipes.)
NB_DIRS   := Workshop/workshop_1 Workshop/workshop_2 Workshop/workshop_3
NB_GLOB   := $(foreach d,$(NB_DIRS),$(d)/*.ipynb)
NB_SCRATCH := $(foreach d,$(NB_DIRS),$(d)/_*.nc $(d)/_traps.csv)
PORT_ARGS := $(if $(filter 5432,$(PORT)),,--port $(PORT))

.DEFAULT_GOAL := all
.PHONY: all setup lab lab-offline notebook notebooks test check check-notebooks check-independence \
        lint unit fresh clean clean-scratch clean-cache help deps kernel prefetch db db-ocean shell \
        beginners ml bonus

## all: set up, then open Jupyter Lab
all: setup lab

## setup: install deps, start the database, load the data, warm the API cache
setup:
	@$(UVRUN) workshop-setup $(PORT_ARGS)

## deps: sync Python dependencies only
deps:
	@$(UV) sync

## kernel: register the Jupyter kernel (setup does this too)
##
## No --user: Jupyter searches the environment data dir before the user one, so a
## --user spec is shadowed by the venv's own python3 and never shows in the picker.
kernel:
	@$(UVRUN) python -m ipykernel install --sys-prefix --name python3 \
		--display-name "Python 3 (ocean-sim)"

## lab: set up and open Jupyter Lab with Workshop as the default folder
##
## lab_root.py runs first because --notebook-dir sets the server root but does not
## beat JupyterLab's own restore of the last directory: one session inside workshop_3/
## and every later launch opened there instead, with the root setting ignored.
lab: setup
	@$(UVRUN) python scripts/lab_root.py
	@$(UVRUN) jupyter lab --notebook-dir=Workshop

## lab-offline: set up and open Jupyter Lab with Workshop as the default folder
##
## The network-is-bad case is also one command. Everything is served from the cache, and
## each request prints a warning saying so -- the numbers are real, just not new.
lab-offline: setup
	@$(UVRUN) python scripts/lab_root.py
	@OCEAN_DATA_WORKSHOP_OFFLINE=1 $(UVRUN) jupyter lab --notebook-dir=Workshop

## beginners: rebuild and run Workshop Intro (5 notebooks, no database)
##
## Separate from `make notebook` on purpose. Workshop Intro assumes no API experience
## and has no dependency on the database, the cache or the Makefile -- it is the
## thing to give someone who has never fetched a URL.
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

## ml: is the MB01 detection task real, or circular?
##
## The feasibility spike behind the next workshop. NOAA's ships/dolphin labels and the
## hourly third-octave levels are BOTH derived from LTSA analysis, so predicting a
## detection from a band level looks like predicting a quantity from itself. This
## measures it instead of arguing about it: if a model approaches 1.0 the task is
## circular, and a plateau short of that means the detector used information the bands
## do not contain.
##
## Not part of `make test` -- it trains models, so it is slow and its output is a
## judgement rather than a pass/fail.
ml:
	@$(UVRUN) python scripts/ml_triviality.py

## bonus: install the optional extras -- PyTorch, for notebook 10
##
## Separate from setup on purpose. torch is a ~200 MB download, and it is needed by
## exactly one notebook, the last of twenty-six, which is labelled a bonus and whose
## subject (classification, clustering) is already taught with scikit-learn in 02 and
## 07. Nobody should wait through that download before starting the workshop, so it is
## opt-in. Notebook 10 runs either way and says which it did.
bonus:
	@$(UV) sync --extra bonus
	@echo "  PyTorch installed -- rerun notebook 10 to see it"

## db-ocean: also load the GLORYS ocean profile -- ~325 MB of transfer
##
## Deliberately separate. It is the slowest thing in setup by an order of magnitude,
## it needs a Copernicus account, and only notebooks 06 and 09 touch it. The
## workshop's headline result -- wind against underwater noise -- needs only wind
## and acoustics, so 08 in particular is unaffected.
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
##
## The notebooks are committed on purpose (build_notebooks.py:6), so this deletes
## tracked files and `git checkout` is how you get them back without rebuilding.
## 'make notebooks' re-renders workshop_2 and workshop_3; 'make beginners' re-renders
## workshop_1. To throw away scratch only and keep the committed output, use
## 'make clean-scratch'.
clean:
	@rm -f $(NB_GLOB)
	@$(MAKE) --no-print-directory clean-scratch
	@echo "  removed the generated notebooks -- 'make notebooks' puts them back"

## clean-scratch: remove cell-written scratch files, keeping the committed notebooks
##
## Deliberately not a `_*` glob: `_fetch.py` and `_sources.py` match it and are tracked
## source, not scratch. Only the .nc a cell writes, and _traps.csv, are removed.
## _traps.csv is itself tracked (written by 10_trap_table.ipynb), so this deletes a
## committed file too; re-run that notebook or `git checkout` to get it back.
clean-scratch:
	@rm -f $(NB_SCRATCH)

## clean-cache: drop the prefetched responses, forcing a live fetch next time
##
## The cache is Workshop/.cache, which is what _fetch.py computes as
## Path(__file__).parent.parent / ".cache" from either workshop dir. This used to point
## at Workshop/workshop_2/.cache, a path that has not existed since the reorg, so it
## silently did nothing and still printed success. The cache is tracked, so 'make
## prefetch' (or git checkout) puts it back.
clean-cache:
	@rm -rf Workshop/.cache
	@echo "  cache cleared -- 'make prefetch' warms it again"

## shell: a Python shell with everything already imported
shell:
	@$(UVRUN) python

## help: list the targets
help:
	@grep -E '^## [a-z-]+:' $(MAKEFILE_LIST) | sed 's/^## /  /' | sort
