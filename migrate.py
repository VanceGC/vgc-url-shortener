#!/usr/bin/env python3
"""
Migration script: Import existing URLs from SQLite dump into MySQL
Usage: python3 migrate.py url_shortener_backup.sql
"""

import sys
import re
import pymysql
import os

DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', '3306'))
DB_USER = os.environ.get('DB_USER', 'vgcto')
DB_PASS = os.environ.get('DB_PASS', 'vgctopass')
DB_NAME = os.environ.get('DB_NAME', 'vgcto')

def parse_sqlite_dump(filename):
    """Extract INSERT statements from SQLite dump"""
    urls = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line.startswith('INSERT INTO url_map VALUES'):
                continue
            # Format: INSERT INTO url_map VALUES(id,'original_url','short');
            match = re.match(r"INSERT INTO url_map VALUES\((\d+),'(.+)','([^']+)'\);?$", line)
            if match:
                id_, original_url, short = match.groups()
                urls.append((original_url, short))
            else:
                print(f"  Warning: could not parse line: {line[:80]}")
    return urls

def migrate(filename):
    print(f"Connecting to MySQL at {DB_HOST}:{DB_PORT}...")
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    print(f"Parsing {filename}...")
    urls = parse_sqlite_dump(filename)
    print(f"Found {len(urls)} URLs to migrate")
    
    imported = 0
    skipped = 0
    
    for original_url, short in urls:
        try:
            cursor.execute(
                "INSERT IGNORE INTO url_map (original_url, short, click_count) VALUES (%s, %s, 0)",
                (original_url, short)
            )
            if cursor.rowcount > 0:
                imported += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error importing {short}: {e}")
            skipped += 1
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\nMigration complete!")
    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 migrate.py url_shortener_backup.sql")
        sys.exit(1)
    migrate(sys.argv[1])
