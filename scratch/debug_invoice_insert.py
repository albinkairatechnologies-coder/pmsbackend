import sys
import os
import json
sys.path.insert(0, r"f:\kaira\deploypms\backend\backend")
from dotenv import load_dotenv
load_dotenv()
from app.utils.database import get_db_connection
from app.models.proposal import Invoice

def test():
    try:
        # Attempt a test create simulating payload
        data = {
            "invoice_date": "2026-05-15",
            "due_date": "2026-05-29",
            "billed_to": {"name": "Test Customer", "company": "Test Co", "email": "", "phone": "", "address": ""},
            "billed_by": {"company": "KAIRA TECHNOLOGIES", "email": "info@kairatechnologies.in", "phone": "6379430293", "address": "Kovilpatti"},
            "line_items": [{"description": "Item 1", "quantity": 1, "unit_price": 1000, "total": 1000}],
            "subtotal": 1000,
            "tax_percent": 18,
            "tax_amount": 180,
            "total_amount": 1180,
            "status": "sent"
        }
        row = Invoice.create(created_by=1, **data)
        print(f"SUCCESS: {row}")
    except Exception as e:
        print(f"ERROR DURING CREATE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test()
