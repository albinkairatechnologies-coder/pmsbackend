import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.utils.database import get_db_connection

def run_migration():
    print("Starting database migration: Upgrading users.role ENUM values...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Print existing schema of users.role
        print("\n[Current schema of users table's role column]:")
        cursor.execute("DESCRIBE users")
        columns = cursor.fetchall()
        role_col = None
        for col in columns:
            if col[0] == 'role':
                role_col = col
                print(col)
        
        # 2. Perform the ALTER TABLE operation
        print("\nAltering users table to include 'bdm', 'video_editor', and 'designer' in the role ENUM...")
        alter_query = """
        ALTER TABLE users 
        MODIFY COLUMN role ENUM(
            'admin', 
            'bdm', 
            'marketing_head', 
            'developer', 
            'smm', 
            'video_editor', 
            'designer', 
            'crm_head', 
            'crm', 
            'client', 
            'team_lead', 
            'employee'
        ) DEFAULT NULL
        """
        cursor.execute(alter_query)
        conn.commit()
        print("Success: Table altered successfully!")
        
        # 3. Print updated schema of users.role
        print("\n[Updated schema of users table's role column]:")
        cursor.execute("DESCRIBE users")
        columns = cursor.fetchall()
        for col in columns:
            if col[0] == 'role':
                print(col)
                
        cursor.close()
    except Exception as e:
        print(f"\nMigration failed with error: {e}")
        conn.rollback()
    finally:
        conn.close()
        print("\nMigration run finished.")

if __name__ == '__main__':
    run_migration()
