# SQL Refactoring Summary

This document describes the refactoring of `learning/schema.sql` into a folder-based structure organized by teaching difficulty.

## Changes Made

### 1. New Folder Structure

```
learning/
├── beginner/           # Basic SQL concepts
│   ├── 01_provenance.sql    (65 lines)
│   ├── 02_ocean_profile.sql (45 lines)
│   └── 03_wind_daily.sql    (51 lines)
├── intermediate/       # Intermediate SQL concepts
│   ├── 04_acoustic.sql      (69 lines)
│   └── 05_detections.sql    (64 lines)
├── advanced/           # Advanced SQL concepts
│   ├── 06_views.sql         (98 lines)
│   └── 07_comments.sql      (82 lines)
├── README.md           # Documentation for SQL curriculum
└── schema.sql          # Original file (kept for compatibility)
```

### 2. New Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `learning/beginner/01_provenance.sql` | 65 | Basic tables, constraints, access classes |
| `learning/beginner/02_ocean_profile.sql` | 45 | Hypertables, time-series data |
| `learning/beginner/03_wind_daily.sql` | 51 | Circular statistics, daily aggregates |
| `learning/intermediate/04_acoustic.sql` | 69 | Wide tables, frequency bands |
| `learning/intermediate/05_detections.sql` | 64 | Event lists vs presence/absence |
| `learning/advanced/06_views.sql` | 98 | Complex joins, window functions |
| `learning/advanced/07_comments.sql` | 82 | Column documentation |
| `learning/README.md` | 141 | Documentation for SQL curriculum |
| `scripts/load_sql_folder.py` | 116 | Loader for folder-based SQL files |

### 3. Teaching Organization

**Beginner (01-03)**
- Basic table creation
- PRIMARY KEY constraints
- CHECK constraints
- Hypertables
- Circular statistics
- Time-series data

**Intermediate (04-05)**
- Wide tables (one column per band)
- Pattern-based naming
- Event lists vs presence/absence
- Composite primary keys
- Aggregation strategies

**Advanced (06-07)**
- Complex JOINs (LEFT JOIN)
- Time-based joins
- Subqueries
- FILTER clause
- Column comments
- View creation

## Usage

### Loading SQL from Folder Structure

```bash
# Load all SQL files (beginner → intermediate → advanced)
uv run python scripts/load_sql_folder.py

# Load only beginner SQL
uv run python scripts/load_sql_folder.py --beginner

# Load only intermediate SQL
uv run python scripts/load_sql_folder.py --intermediate

# Load only advanced SQL
uv run python scripts/load_sql_folder.py --advanced

# Load from custom path
uv run python scripts/load_sql_folder.py --path learning/beginner
```

### Comparing with Original Schema

The original `learning/schema.sql` file is still present and unchanged. To use it:

```bash
# Original method
uv run python scripts/load_db.py
```

The folder-based approach provides:
- **Modularity**: Teach SQL concepts incrementally
- **Organization**: Group by difficulty level
- **Clarity**: Each file has a clear teaching objective
- **Flexibility**: Load subsets of SQL (e.g., beginner-only for intro courses)

## Benefits

1. **Better Organization**: SQL concepts grouped by difficulty
2. **Teaching Flexibility**: Instructors can load only relevant SQL
3. **Clear Progression**: Beginner → Intermediate → Advanced
4. **Documentation**: README.md explains the curriculum
5. **Backward Compatibility**: Original schema.sql remains

## Total Code

- **SQL files**: 524 lines (across 7 files)
- **Python loader**: 116 lines
- **Documentation**: 141 lines
- **Total new code**: ~780 lines

## Next Steps

- [ ] Test the loader with an actual database
- [ ] Update workshop materials to reference new folder structure
- [ ] Consider deprecating old schema.sql after validation
- [ ] Add SQL file tests
