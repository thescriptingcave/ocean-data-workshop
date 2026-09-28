# Data Access Inventory

**GENERATED** by `uv run python -m probes.run_all` -- do not hand-edit.
Shows the most recent result per probe. Written verdicts live in `VERDICTS.md`.

Access classes: **A** anonymous HTTP · **B** anonymous, other protocol ·
**C** free account + password · **D** account + API key · **E** terms/approval ·
**F** manual request · **G** licensed · **H** unavailable

| | probe | class | provides | verdict |
|---|---|---|---|---|
| [x] | **gsw** — gsw / TEOS-10 thermodynamic toolbox | A | sound speed, in-situ & potential density, SA/CT/SP conversions | PASS in 0.0s || [x] | **erddap** — ERDDAP griddap service (NOAA CoastWatch) | A | HTTP access to thousands of gridded ocean/atmospheric datasets | PASS in 5.0s || [x] | **sst_erddap** — Sea surface temperature at Monterey Bay via ERDDAP (jplMURSST41) | A | daily analysed SST, 0.045 deg, 2002-present | PASS in 1.3s || [x] | **toolchain** — PostgreSQL + TimescaleDB + psycopg + plotly | A | operational time-series store and interactive plotting | PASS in 0.2s || [x] | **ncei_pad** — NOAA NCEI Passive Acoustic Data archive (GCS bucket) | A | raw hydrophone audio, sound-level metrics, and species/vessel detections | PASS in 0.5s || [x] | **ncei_labels** — NCEI SanctSound detection labels (dolphin / ship) | A | hourly presence/absence labels per species and per vessel | PASS in 0.2s || [x] | **argo_gdac** — Argo in-situ profiles via GDAC | A | T/S/pressure profiles to 2000 m, ~10-day cycles, with QC flags | PASS in 0.0s || [x] | **glorys** — GLORYS12V1 global ocean reanalysis (Copernicus Marine) | C | daily T/S/currents/SSH, 1/12 deg, 50 levels, 1993-present | PASS in 28.1s || [x] | **ncei_metadata** — SanctSound file-level metadata index (site catalogue) | A | coordinates, sensor depth, sample rate, dates for 25,503 recording files | PASS in 0.0s |
**9/9 passing.**
