from app.utils.database import get_db_connection
import json
import sys

def check_feedback():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        results = {}
        for table in ['feedback', 'review_meetings']:
            cursor.execute(f"DESCRIBE {table}")
            results[table] = cursor.fetchall()
        
        print(json.dumps(results, indent=2))
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    sys.path.append(".")
    check_feedback()
