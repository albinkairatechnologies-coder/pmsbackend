from app.utils.database import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("DESCRIBE task_messages")
for row in cursor.fetchall():
    print(row)
cursor.close()
conn.close()
