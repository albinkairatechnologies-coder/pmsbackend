import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.utils.database import get_db_connection

def run_migration():
    print("Starting database migration: Upgrading users role and company settings schemas...")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Alter users.role enum to add 'bdm_head'
        print("\nChecking and altering users table to include 'bdm_head' in the role ENUM...")
        alter_users_query = """
        ALTER TABLE users 
        MODIFY COLUMN role ENUM(
            'admin', 
            'bdm_head',
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
        try:
            cursor.execute(alter_users_query)
            conn.commit()
            print("Success: users table altered successfully!")
        except Exception as e:
            print(f"Altering users table failed (might be already altered): {e}")
            conn.rollback()

        # 2. Check and add role_permissions column to company_settings
        print("\nChecking if 'role_permissions' column exists in company_settings table...")
        cursor.execute("DESCRIBE company_settings")
        columns = cursor.fetchall()
        has_role_permissions = any(col[0] == 'role_permissions' for col in columns)
        
        if not has_role_permissions:
            print("Adding 'role_permissions' column to company_settings table...")
            alter_settings_query = "ALTER TABLE company_settings ADD COLUMN role_permissions TEXT DEFAULT NULL"
            cursor.execute(alter_settings_query)
            conn.commit()
            print("Success: 'role_permissions' column added to company_settings!")
        else:
            print("Info: 'role_permissions' column already exists in company_settings.")
            
        cursor.close()
    except Exception as e:
        print(f"\nMigration failed with error: {e}")
        conn.rollback()
    finally:
        conn.close()
        print("\nMigration run finished.")

if __name__ == '__main__':
    run_migration()
