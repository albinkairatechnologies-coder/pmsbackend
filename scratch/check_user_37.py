import sys
sys.path.append('.')
from app.utils.database import get_db_connection

def main():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch user 37 details
    cursor.execute("SELECT * FROM users WHERE id = 37")
    user = cursor.fetchone()
    print("--- USER 37 DETAILS ---")
    if user:
        for k, v in user.items():
            print(f"{k}: {repr(v)}")
    else:
        print("User 37 not found in database.")
        
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
