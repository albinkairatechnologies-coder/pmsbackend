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
        print("Checking/Altering clients table to add tracking_token column...")
        # Check if the column already exists
        cursor.execute("SHOW COLUMNS FROM clients LIKE 'tracking_token'")
        column_exists = cursor.fetchone()

        if not column_exists:
            print("Adding tracking_token column to clients table...")
            cursor.execute("""
                ALTER TABLE clients 
                ADD COLUMN tracking_token VARCHAR(64) UNIQUE NULL
            """)
            conn.commit()
            print("Column 'tracking_token' added successfully to clients table.")
        else:
            print("Column 'tracking_token' already exists in clients table.")

        # Backfill existing clients with tracking tokens
        print("Checking for existing clients that require a tracking token...")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, company_name FROM clients WHERE tracking_token IS NULL")
        clients_to_backfill = cursor.fetchall()

        if clients_to_backfill:
            print(f"Found {len(clients_to_backfill)} clients to backfill.")
            cursor2 = conn.cursor()
            for client in clients_to_backfill:
                token = secrets.token_hex(16)
                cursor2.execute(
                    "UPDATE clients SET tracking_token = %s WHERE id = %s",
                    (token, client['id'])
                )
                print(f"  -> Generated token for client '{client['company_name']}' (id: {client['id']})")
            conn.commit()
            cursor2.close()
            print("Backfill completed successfully.")
        else:
            print("No clients require backfilling.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run()
