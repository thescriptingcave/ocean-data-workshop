# How to Run SQL Files in TablePlus

## Connection Details
- **Host**: localhost
- **Port**: 5432
- **Database**: ocean_data_workshop
- **Username**: postgres
- **Password**: ocean

## Steps to Run

### Method 1: Run Files One by One (Recommended)

1. **Connect** to the database using the details above
2. Open each SQL file in your text editor
3. **Copy** the entire content of the file
4. **Paste** into TablePlus's SQL query window
5. Click **Run** (or press Cmd+R on Mac)
6. Wait for "Query Successful" message
7. Repeat for each file

### File Order (Important!)

Run these files in this exact order:

**Level 1 - Beginner (4 tables):**
1. `learning/beginner/01_provenance.sql`
2. `learning/beginner/02_ocean_profile.sql`
3. `learning/beginner/03_wind_daily.sql`

**Level 2 - Intermediate (2 more tables):**
4. `learning/intermediate/04_acoustic.sql`
5. `learning/intermediate/05_detections.sql`

**Level 3 - Advanced (2 views):**
6. `learning/advanced/06_views.sql`
7. `learning/advanced/07_comments.sql`

### Method 2: Copy All SQL Files Into One Query

Open all SQL files in your text editor, copy their contents, and paste into one query window in TablePlus. The files are already in the correct order (01, 02, 03, etc.).

## Quick Reference

### What Each File Teaches:

| File | Tables/Views | Concepts |
|------|--------------|----------|
| 01_provenance.sql | source, run | Basic tables, constraints |
| 02_ocean_profile.sql | ocean_profile_daily | Hypertables, time-series |
| 03_wind_daily.sql | wind_daily | Circular statistics |
| 04_acoustic.sql | acoustic_tol_hourly | Wide tables (30 columns) |
| 05_detections.sql | detection_hourly | Event lists vs presence/absence |
| 06_views.sql | v_site_hourly, v_daily_environment | Complex JOINs, window functions |
| 07_comments.sql | (comments) | Documentation |

### Expected Result

After running all files, you should see:
- **6 tables**: source, run, ocean_profile_daily, wind_daily, acoustic_tol_hourly, detection_hourly
- **2 views**: v_site_hourly, v_daily_environment

## Troubleshooting

### "table already exists" error
- Solution: You've already run this file. Run "Drop Tables" script first, or just continue.

### "relation does not exist" error
- Solution: You're trying to run a file before its dependencies. Run files in order.

### Connection Failed
- Make sure Docker container is running: `docker-compose ps`
- Restart database: `docker-compose restart db`

## Visual Guide

```
TablePlus Window:
┌─────────────────────────────────────────────┐
│  [Connection]  [Query Tab]  [Results Tab]  │
│                                             │
│  1. Copy SQL file content                  │
│  2. Paste into Query Tab                   │
│  3. Click Run button (Cmd+R)              │
│  4. See results in Results Tab             │
└─────────────────────────────────────────────┘
```

## Next Steps

After running the SQL files:
1. Check the "Tables" sidebar to see all tables
2. Click on each table to view its structure
3. Click on "Data" tab to see the data (will be empty initially)
4. Run the data loader: `uv run python scripts/load_db.py`

## Help

For more information, see:
- `learning/README.md` - SQL curriculum documentation
- `SQL_TEST_REPORT.md` - Test results
