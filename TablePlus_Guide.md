# TablePlus Guide for Ocean Data Workshop

## Quick Start (30 seconds)

### Step 1: Connect to Database
```
Host:     localhost
Port:     5432
Database: ocean_data_workshop
Username: postgres
Password: ocean
```

### Step 2: Open SQL File
Open one of these files:
- **Full SQL**: `learning/all_sql_combined.sql` (all at once)
- **Beginner**: `learning/beginner/01_provenance.sql`
- **Intermediate**: `learning/intermediate/04_acoustic.sql`
- **Advanced**: `learning/advanced/06_views.sql`

### Step 3: Copy & Run
1. **Copy** the entire SQL file content
2. **Paste** into TablePlus query window
3. **Click Run** (Cmd+R on Mac)
4. Done!

## Complete Connection Details

| Setting | Value |
|---------|-------|
| Host | `localhost` |
| Port | `5432` |
| Database | `ocean_data_workshop` |
| Username | `postgres` |
| Password | `ocean` |

## File Options

### Option A: All SQL at Once
Open: `learning/all_sql_combined.sql`
- Contains all 200 lines of SQL
- Runs all tables and views in correct order
- Single click to run everything

### Option B: Level by Level
**Beginner Level:**
- `learning/beginner/01_provenance.sql` - 2 tables
- `learning/beginner/02_ocean_profile.sql` - 1 table
- `learning/beginner/03_wind_daily.sql` - 1 table

**Intermediate Level:**
- `learning/intermediate/04_acoustic.sql` - 1 table
- `learning/intermediate/05_detections.sql` - 1 table

**Advanced Level:**
- `learning/advanced/06_views.sql` - 2 views
- `learning/advanced/07_comments.sql` - Documentation

## What You'll See

After running the SQL, you should see:

### Tables (6)
1. `source` - Data provenance
2. `run` - Query history
3. `ocean_profile_daily` - Ocean data
4. `wind_daily` - Wind data
5. `acoustic_tol_hourly` - Acoustic data (34 columns!)
6. `detection_hourly` - Animal detections

### Views (2)
1. `v_site_hourly` - Combined hourly data
2. `v_daily_environment` - Daily summary

## Visual Guide

```
TablePlus Window:

┌──────────────────────────────────────────────────────┐
│ [+] [/mysql] [postgres] [localhost] [_oct]         │ ← Connections
├──────────────────────────────────────────────────────┤
│  Tables                                              │
│  ├── source                                          │
│  ├── run                                             │
│  ├── ocean_profile_daily                            │
│  ├── wind_daily                                     │
│  ├── acoustic_tol_hourly                            │
│  ├── detection_hourly                               │
│  │                                                   │
│  Views                                               │
│  ├── v_site_hourly                                  │
│  └── v_daily_environment                            │
│                                                      │
│  Query                                               │ ← Paste SQL here
│  SELECT * FROM source;               [Run] [Cmd+R] │
└──────────────────────────────────────────────────────┘

Click on a table to:
- View structure (columns, types)
- See data (empty initially)
- Export to CSV
```

## Common Tasks

### View Table Structure
1. Click on table name in sidebar
2. Click "Structure" tab
3. See all columns with types and comments

### View Sample Data
1. Click on table name
2. Click "Data" tab
3. See first 100 rows (will be empty initially)

### Run Custom Query
1. Click "Query" tab (or Cmd+T)
2. Type your SQL
3. Click "Run" (Cmd+R)

Example queries:
```sql
-- List all tables
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

-- Check table row counts
SELECT 'source' as table_name, COUNT(*) as rows FROM source
UNION ALL SELECT 'wind_daily', COUNT(*) FROM wind_daily;
```

## Troubleshooting

### "Connection Refused"
- Make sure Docker is running: `docker-compose ps`
- Wait 5 seconds for database to start
- Try reconnecting

### "Table Already Exists"
- You've already run this SQL
- Either continue or drop tables first

### "Column Not Found"
- You're trying to query before data is loaded
- Run the data loader: `uv run python scripts/load_db.py`

## Next Steps

After running SQL files:
1. Check all tables exist in sidebar
2. Click "Data" tab on each table
3. Run data loader to populate tables
4. Start exploring the data!

## Quick Commands Reference

| Action | Shortcut |
|--------|----------|
| Run query | Cmd+R (Mac) / Ctrl+R (Win) |
| New query tab | Cmd+T (Mac) / Ctrl+T (Win) |
| Switch to Data tab | Click "Data" |
| Switch to Structure tab | Click "Structure" |
| Export to CSV | Click ⋯ → Export |
| Refresh connection | Click refresh icon |

## Need Help?

- `learning/README.md` - SQL curriculum docs
- `learning/Run_In_TablePlus.md` - Detailed guide
- `SQL_TEST_REPORT.md` - Test results

---

**Connection Summary:**
```
TablePlus → New Connection → PostgreSQL
Host: localhost
Port: 5432
Database: ocean_data_workshop
Username: postgres
Password: ocean
```
