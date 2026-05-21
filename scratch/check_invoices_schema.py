from app.utils.database import get_db_connection
import json
import sys

def check_invoices():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        tables = ['invoices']
        results = {}
        for table in tables:
            try:
                cursor.execute(f"DESCRIBE {table}")
                results[table] = cursor.fetchall()
            except Exception as e:
                results[table] = f"Error: {str(e)}"
        print(json.dumps(results, indent=2))
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    sys.path.append(".")
    check_invoices()
