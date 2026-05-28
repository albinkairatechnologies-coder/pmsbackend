from app.utils.database import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
try:
    print("Altering task_messages table...")
    cursor.execute("ALTER TABLE task_messages ADD COLUMN is_read INT DEFAULT 0")
    conn.commit()
    print("Altered task_messages successfully!")
except Exception as e:
    print("Error during alter:", e)
finally:
    cursor.close()
    conn.close()
