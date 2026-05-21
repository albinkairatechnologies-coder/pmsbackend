import sys
import json
import traceback

def test_client_serialization():
    try:
        from app.models.client import Client
        clients = Client.get_all()
        print(f"Loaded {len(clients)} clients from DB.")
        
        print("Attempting to serialize to JSON...")
        serialized = json.dumps(clients)
        print("SUCCESS! Serialization worked.")
        
    except Exception as e:
        print("\n--- SERIALIZATION ERROR ---")
        traceback.print_exc()

if __name__ == "__main__":
    sys.path.append(".")
    test_client_serialization()
