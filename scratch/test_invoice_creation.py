import sys
import json
import traceback

def test_create_invoice():
    try:
        from app.models.proposal import Invoice
        from app.utils.database import get_db_connection
        
        # Try creating an invoice dummy record
        payload = {
            'client_id': 1,
            'invoice_date': '2026-05-13',
            'due_date': '2026-05-27',
            'billed_to': {'name': 'Test Customer', 'company': 'Test Co'},
            'billed_by': {'company': 'Test Company'},
            'line_items': [{'description': 'Test Service', 'quantity': 1, 'unit_price': 100, 'total': 100}],
            'subtotal': 100,
            'tax_percent': 18,
            'tax_amount': 18,
            'total_amount': 118,
            'status': 'sent'
        }
        
        # Created by admin_id (usually 1)
        print("Invoking Invoice.create...")
        row = Invoice.create(created_by=1, **payload)
        print("SUCCESS! Created row:", row)
        
        # Clean it up
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM invoices WHERE id = %s", (row['id'],))
        conn.commit()
        cur.close(); conn.close()
        print("Cleanup complete!")
        
    except Exception as e:
        print("\n--- ERROR DETECTED ---")
        traceback.print_exc()

if __name__ == "__main__":
    sys.path.append(".")
    test_create_invoice()
