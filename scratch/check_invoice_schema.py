import sys
import os
sys.path.insert(0, r"f:\kaira\deploypms\backend\backend")
from dotenv import load_dotenv
load_dotenv()
from app.utils.database import get_db_connection

def check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DESCRIBE invoices")
        for col in cursor.fetchall():
            print(col)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check()
