#!/usr/bin/env python3
"""Load SQL schema from folder structure.

This script loads SQL files from learning/beginner/, learning/intermediate/,
and learning/advanced/ directories in order.

Usage:
    uv run python scripts/load_sql_folder.py
    uv run python scripts/load_sql_folder.py --path learning/beginner
    uv run python scripts/load_sql_folder.py --path learning/advanced
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg

# Add src to path for imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ocean_data_workshop.dsn import dsn


def load_sql_from_folder(folder: Path) -> int:
    """Load all SQL files from a folder in alphabetical order."""
    if not folder.exists():
        print(f"Error: Folder not found: {folder}")
        return 1
    
    sql_files = sorted(folder.glob("*.sql"))
    
    if not sql_files:
        print(f"No SQL files found in: {folder}")
        return 0
    
    DSN = dsn()
    total_lines = 0
    
    print(f"Loading SQL from: {folder}")
    print(f"Found {len(sql_files)} SQL file(s)")
    
    with psycopg.connect(DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            for sql_file in sql_files:
                content = sql_file.read_text()
                lines = len(content.splitlines())
                print(f"  {sql_file.name}: {lines} lines")
                
                try:
                    cur.execute(content)
                    total_lines += lines
                except Exception as e:
                    print(f"  ERROR executing {sql_file.name}:")
                    print(f"    {type(e).__name__}: {str(e)}")
                    return 1
    
    print(f"\nLoaded {total_lines} lines from {len(sql_files)} file(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load SQL schema from folder structure"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(ROOT / "learning"),
        help="Path to SQL folder (default: learning/ - loads all folders)",
    )
    parser.add_argument(
        "--beginner",
        action="store_true",
        help="Load only beginner folder",
    )
    parser.add_argument(
        "--intermediate",
        action="store_true",
        help="Load only intermediate folder",
    )
    parser.add_argument(
        "--advanced",
        action="store_true",
        help="Load only advanced folder",
    )
    
    args = parser.parse_args()
    
    if args.beginner:
        return load_sql_from_folder(ROOT / "learning" / "beginner")
    elif args.intermediate:
        return load_sql_from_folder(ROOT / "learning" / "intermediate")
    elif args.advanced:
        return load_sql_from_folder(ROOT / "learning" / "advanced")
    else:
        # Load all folders in order
        folders = [
            ROOT / "learning" / "beginner",
            ROOT / "learning" / "intermediate",
            ROOT / "learning" / "advanced",
        ]
        
        for folder in folders:
            result = load_sql_from_folder(folder)
            if result != 0:
                return result
        
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
