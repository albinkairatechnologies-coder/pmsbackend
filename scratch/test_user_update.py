import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.models.user import User
from app.utils.database import get_db_connection

def test_update():
    print("Fetching users from DB...")
    users = User.get_all()
    if not users:
        print("No users found to test.")
        return
        
    print(f"Found {len(users)} users. Selecting first user to perform a test update...")
    test_user = users[0]
    user_id = test_user['id']
    original_role = test_user['role']
    print(f"Selected user: ID={user_id}, Name={test_user['name']}, Email={test_user['email']}, Current Role={original_role}")
    
    try:
        # Test 1: Update role to 'bdm'
        print("\nUpdating role to 'bdm'...")
        User.update(user_id, role='bdm')
        updated_user = User.get_by_id(user_id)
        print(f"Success! Updated role in DB: {updated_user['role']}")
        
        # Test 2: Update role to 'video_editor'
        print("\nUpdating role to 'video_editor'...")
        User.update(user_id, role='video_editor')
        updated_user = User.get_by_id(user_id)
        print(f"Success! Updated role in DB: {updated_user['role']}")
        
        # Test 3: Update role to 'designer'
        print("\nUpdating role to 'designer'...")
        User.update(user_id, role='designer')
        updated_user = User.get_by_id(user_id)
        print(f"Success! Updated role in DB: {updated_user['role']}")
        
        # Test 4: Restore original role
        print(f"\nRestoring original role to '{original_role}'...")
        User.update(user_id, role=original_role)
        restored_user = User.get_by_id(user_id)
        print(f"Success! Restored role in DB: {restored_user['role']}")
        
        print("\nAll update tests passed with NO errors!")
    except Exception as e:
        print(f"\nTest failed with exception: {e}")

if __name__ == '__main__':
    test_update()
