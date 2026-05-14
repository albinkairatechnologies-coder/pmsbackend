from app.utils.database import get_db_connection
import json
import sys

def check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES")
        tables = [list(r.values())[0] for r in cursor.fetchall()]
        print("Tables in DB:", tables)

        results = {}
        for table in ['campaigns', 'expenses']:
            if table in tables:
                cursor.execute(f"DESCRIBE {table}")
                results[table] = cursor.fetchall()
            else:
                results[table] = "TABLE DOES NOT EXIST"
        
        print(json.dumps(results, indent=2))
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    sys.path.append(".")
    check()
