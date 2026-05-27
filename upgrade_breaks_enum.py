from app.utils.database import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
try:
    print("Altering breaks table schema...")
    cursor.execute("ALTER TABLE breaks MODIFY COLUMN break_type ENUM('lunch', 'short', 'meeting') NOT NULL")
    conn.commit()
    print("Altered breaks table successfully!")
except Exception as e:
    print("Error during alter:", e)
finally:
    cursor.close()
    conn.close()
