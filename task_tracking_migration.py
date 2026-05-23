import sys
import os
import secrets
from dotenv import load_dotenv

# Ensure the backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()
from app.utils.database import get_db_connection

def run():
    print("Connecting to database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        print("Checking/Altering tasks table to add tracking_token column...")
        # Check if the column already exists
        cursor.execute("SHOW COLUMNS FROM tasks LIKE 'tracking_token'")
        column_exists = cursor.fetchone()

        if not column_exists:
            print("Adding tracking_token column to tasks table...")
            cursor.execute("""
                ALTER TABLE tasks 
                ADD COLUMN tracking_token VARCHAR(64) UNIQUE NULL
            """)
            conn.commit()
            print("Column 'tracking_token' added successfully.")
        else:
            print("Column 'tracking_token' already exists.")

        # Backfill existing tasks with tracking tokens
        print("Checking for existing tasks that require a tracking token...")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, title FROM tasks WHERE tracking_token IS NULL")
        tasks_to_backfill = cursor.fetchall()

        if tasks_to_backfill:
            print(f"Found {len(tasks_to_backfill)} tasks to backfill.")
            cursor2 = conn.cursor()
            for task in tasks_to_backfill:
                token = secrets.token_hex(16)
                cursor2.execute(
                    "UPDATE tasks SET tracking_token = %s WHERE id = %s",
                    (token, task['id'])
                )
                print(f"  -> Generated token for task '{task['title']}' (id: {task['id']})")
            conn.commit()
            cursor2.close()
            print("Backfill completed successfully.")
        else:
            print("No tasks require backfilling.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run()
