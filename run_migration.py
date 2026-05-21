"""
run_migration.py
Run this once to apply superadmin_migration.sql to your database.
Usage:  python run_migration.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.utils.database import get_db_connection

SQL_FILE = os.path.join(os.path.dirname(__file__), 'superadmin_migration.sql')


def run():
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove comment lines, split by semicolon
    lines = [l for l in content.splitlines() if not l.strip().startswith('--') and not l.strip().startswith('/*') and not l.strip().startswith('*')]
    clean_sql = '\n'.join(lines)
    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]

    conn = get_db_connection()
    cursor = conn.cursor()
    success = 0
    skipped = 0

    print(f"\nRunning migration: {SQL_FILE}\n{'─'*50}")
    for stmt in statements:
        try:
            cursor.execute(stmt)
            conn.commit()
            first_line = stmt.splitlines()[0][:70]
            print(f"  ✓  {first_line}")
            success += 1
        except Exception as e:
            err = str(e)
            # Ignore "already exists" errors — safe to re-run
            if 'already exists' in err.lower() or 'duplicate' in err.lower() or '1060' in err:
                print(f"  ~  SKIP (already exists): {stmt.splitlines()[0][:60]}")
                skipped += 1
            else:
                print(f"  ✗  ERROR: {err}")
                print(f"     Statement: {stmt[:80]}")

    cursor.close()
    conn.close()
    print(f"\n{'─'*50}")
    print(f"Migration complete: {success} executed, {skipped} skipped.")
    print("\nNext step: python seeder.py --superadmin")


if __name__ == '__main__':
    run()
