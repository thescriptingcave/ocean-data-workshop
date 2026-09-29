import pathlib

p = pathlib.Path("scripts/workshop_notebooks.py")
s = p.read_text()

BANDS = [25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
         1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500,
         16000, 20000]
values = ", ".join(f"({b}, a.band_{b}hz)" for b in BANDS)
# wrap to keep the line readable in the notebook
values_wrapped = ",\n           ".join(
    ", ".join(f"({b}, a.band_{b}hz)" for b in BANDS[i:i + 5])
    for i in range(0, len(BANDS), 5)
)

# --- replace the row-count cell's band count query ------------------------
old = '''print("  bands available:", q("SELECT count(DISTINCT band_hz) AS n FROM acoustic_tol_hourly")["n"][0])'''
new = '''band_cols = [c for c in pd.read_sql_query(
    "SELECT * FROM acoustic_tol_hourly LIMIT 0", conn).columns if c.startswith("band_")]
print(f"  frequency bands: {len(band_cols)} columns, {band_cols[0]} .. {band_cols[-1]}")'''
assert old in s
s = s.replace(old, new, 1)

# --- replace the "join wind to noise, band by band" cell -------------------
start = s.index('        code(\'\'\'\nconn = psycopg.connect(dsn())\nbands = q("""')
end = s.index("'''),", s.index('print(bands.head(6).to_string(index=False))', start)) + len("'''),")

new_cell = f'''        code(\'\'\'
# The acoustic table is WIDE: one column per band, band_25hz .. band_20000hz.
# That is a reasonable physical layout -- each band is a measured channel -- but it
# means you cannot GROUP BY a band that does not exist as a row.
print("  wide layout:", ", ".join(band_cols[:5]), "...")
print()
print("  To get one row per (day, band) you have to unpivot. The idiomatic way in")
print("  Postgres is CROSS JOIN LATERAL over a VALUES list:")
print()
print("""    CROSS JOIN LATERAL (VALUES
               {values_wrapped}
           ) AS b(hz, db)""")
\'\'\'),'''
s = s[:start] + new_cell + s[end:]

# --- replace the per_band query cell with the real unpivot query ----------
start = s.index("        code('''\n# The correlation, per band.")
end = s.index("'''),", s.index("print('  joined frame:', per_band.shape)", start)) + len("'''),")

new_cell = f'''        code(\'\'\'
conn = psycopg.connect(dsn())
joined = q("""
    SELECT a.observed_at::date AS day,
           w.wind_speed_mean_ms AS wind,
           b.hz AS band_hz,
           b.db  AS level_db
    FROM acoustic_tol_hourly a
    JOIN wind_daily w
      ON w.observed_at = a.observed_at::date
     AND w.station_id = '46092'
    CROSS JOIN LATERAL (VALUES
           {values_wrapped}
           ) AS b(hz, db)
    WHERE b.db IS NOT NULL
""")
conn.close()
print("  joined:", joined.shape, "= (days x bands) long-format rows")
print(joined.head(5).to_string(index=False))
\'\'\'),'''
s = s[:start] + new_cell + s[end:]

# --- the correlation loop should use `joined` (long) instead of `aligned` ---
old_loop = '''results = []
for col in aligned.columns:
    x, y = aligned["wind"].to_numpy(), aligned[col].to_numpy()
    if np.nanstd(y) == 0:
        continue
    r = float(np.corrcoef(x, y)[0, 1])
    # Block bootstrap, not a plain permutation test: the series are autocorrelated, so
    # resampling individual days would destroy the dependence the test has to respect.
    boot = block_bootstrap_pvalue(x, y, max_lag=3, n_boot=300, seed=7)
    results.append((int(col[1:]), r, boot["p_boot"], boot["n_eff_x"]))'''

new_loop = '''# Pivot the long join back to one column per band so each band is a series.
wide = joined.pivot_table(index="day", columns="band_hz",
                          values="level_db", aggfunc="mean")
wide.columns = [f"b{int(c)}" for c in wide.columns]
wide.index = pd.to_datetime(wide.index)
aligned = wide.join(wind, how="inner").dropna()
print(f"  {len(aligned)} days, {aligned.shape[1] - 1} bands\\n")

results = []
for col in aligned.columns.drop("wind"):
    x, y = aligned["wind"].to_numpy(), aligned[col].to_numpy()
    if np.nanstd(y) == 0:
        continue
    r = float(np.corrcoef(x, y)[0, 1])
    # Block bootstrap, not a plain permutation test: the series are autocorrelated, so
    # resampling individual days would destroy the dependence the test has to respect.
    boot = block_bootstrap_pvalue(x, y, max_lag=3, n_boot=300, seed=7)
    results.append((int(col[1:]), r, boot["p_boot"], boot["n_eff_x"]))'''
assert old_loop in s
s = s.replace(old_loop, new_loop, 1)

p.write_text(s)
print("patched 08 for the wide schema")
