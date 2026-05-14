from app.utils.database import get_db_connection
import json

def dump_schema():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    tables = ['leads', 'clients', 'users', 'client_payments', 'tasks']
    schema = {}
    for table in tables:
        try:
            cursor.execute(f"DESCRIBE {table}")
            schema[table] = cursor.fetchall()
        except Exception as e:
            schema[table] = str(e)
    
    print(json.dumps(schema, indent=2))
    cursor.close()
    conn.close()

if __name__ == "__main__":
    dump_schema()
