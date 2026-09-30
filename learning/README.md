# SQL Curriculum for Ocean Data Workshop

This directory contains the SQL curriculum organized by difficulty level.

## Folder Structure

```
learning/
├── beginner/
│   ├── 01_provenance.sql     # Query examples for provenance
│   ├── 02_ocean_profile.sql  # Query examples for ocean data
│   └── 03_wind_daily.sql     # Query examples for wind data
├── intermediate/
│   ├── 04_acoustic.sql       # Query examples for acoustic data
│   └── 05_detections.sql     # Query examples for detections
├── advanced/
│   ├── 06_views.sql          # Query examples for views
│   ├── 07_comments.sql       # Query examples for comments
│   └── 08_ctes.sql           # Query examples for CTEs
├── all_sql_combined.sql      # All queries in one file (recommended for TablePlus)
└── schema.sql                # Original monolithic schema (kept for compatibility)
```

## Beginner SQL (01-03)

**Prerequisites**: Basic SQL knowledge

### 01 Provenance
- Query examples for `source` and `run` tables
- Access classes (A-H) for data accessibility
- Filtering with WHERE, sorting with ORDER BY

### 02 Ocean Profile
- Query examples for `ocean_profile_daily`
- Subqueries in WHERE clause
- Type casting with `::date`
- Aggregation with GROUP BY
- MIN/MAX functions
- BETWEEN for range queries
- Aliasing columns (AS)

### 03 Wind Daily
- Query examples for `wind_daily`
- Circular statistics
- DATE_TRUNC for time aggregation
- Aggregation functions (AVG, MAX, COUNT)

## Intermediate SQL (04-05)

**Prerequisites**: Beginner SQL concepts

### 04 Acoustic
- Query examples for `acoustic_tol_hourly` (30 frequency bands)
- Wide table structure
- UNION for unpivoting
- Multiple band selection

### 05 Detections
- Query examples for `detection_hourly`
- Event lists vs presence/absence
- CAST for type conversion
- COUNT with GROUP BY for rate calculations

## Advanced SQL (06-08)

**Prerequisites**: Intermediate SQL concepts

### 06 Views
- Query examples for `v_site_hourly` and `v_daily_environment`
- Complex JOINs
- Window functions (LAG, AVG OVER)
- Correlation analysis (corr)

### 07 Comments
- Query examples for viewing column comments
- pg_catalog for metadata
- Self-documenting queries

### 08 CTEs (NEW!)
- Simple CTEs for readability
- Multiple CTEs in one query
- Recursive CTEs for sequences
- CTEs with window functions
- CROSS JOIN with CTEs
- INTERSECT with CTEs
- CTEs for correlation analysis
- CTEs as building blocks for complex queries

## Usage in TablePlus

### Quick Start
1. **Open TablePlus**
2. **Connect** to:
   ```
   Host:     localhost
   Port:     5432
   Database: ocean_data_workshop
   Username: postgres
   Password: ocean
   ```
3. **Open** `learning/all_sql_combined.sql`
4. **Copy & Paste** into a query tab
5. **Click Run** (Cmd+R)

### Level by Level
Run the SQL files in order:
1. beginner/01_provenance.sql
2. beginner/02_ocean_profile.sql
3. beginner/03_wind_daily.sql
4. intermediate/04_acoustic.sql
5. intermediate/05_detections.sql
6. advanced/06_views.sql
7. advanced/07_comments.sql
8. advanced/08_ctes.sql

## Database Status

The database already contains:
- **6 Tables**: source, run, ocean_profile_daily, wind_daily, acoustic_tol_hourly, detection_hourly
- **2 Views**: v_site_hourly, v_daily_environment

All SQL files are **query examples** for learning SQL concepts, not CREATE statements.

## Files

| File | Purpose |
|------|---------|
| `learning/all_sql_combined.sql` | All queries in one file (includes CTEs) |
| `learning/beginner/*.sql` | Basic SQL concepts |
| `learning/intermediate/*.sql` | Intermediate SQL concepts |
| `learning/advanced/*.sql` | Advanced SQL concepts |
| `learning/schema.sql` | Original schema (for reference) |
