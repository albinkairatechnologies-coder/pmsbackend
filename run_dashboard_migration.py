import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app.utils.database import get_db_connection

SQL_FILE = os.path.join(os.path.dirname(__file__), 'dashboard_features_migration.sql')

def run():
    if not os.path.exists(SQL_FILE):
        print(f"Error: {SQL_FILE} not found.")
        return

    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = [l for l in content.splitlines() if not l.strip().startswith('--') and not l.strip().startswith('/*') and not l.strip().startswith('*')]
    clean_sql = '\n'.join(lines)
    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]

    conn = get_db_connection()
    cursor = conn.cursor()
    success = 0
    skipped = 0

    print(f"\nRunning dashboard features migration: {SQL_FILE}")
    print("-" * 50)
    for stmt in statements:
        try:
            cursor.execute(stmt)
            conn.commit()
            print(f"  v  {stmt.splitlines()[0][:70]}")
            success += 1
        except Exception as e:
            err = str(e)
            if 'already exists' in err.lower() or 'duplicate' in err.lower() or '1060' in err or '1061' in err:
                print(f"  ~  SKIP (already exists/duplicate): {stmt.splitlines()[0][:60]}")
                skipped += 1
            else:
                print(f"  x  ERROR: {err}")
                print(f"     Statement: {stmt[:80]}")

    cursor.close()
    conn.close()
    print("-" * 50)
    print(f"Migration complete: {success} executed, {skipped} skipped.")

if __name__ == '__main__':
    run()
