from app.utils.database import get_db_connection
from datetime import date, timedelta
import random

def seed_marketing_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get a user and org
    cursor.execute("SELECT id, organisation_id FROM users WHERE role='admin' LIMIT 1")
    user = cursor.fetchone()
    if not user:
        print("No admin user found. Please run main seeder first.")
        return
    
    user_id, org_id = user
    
    # 1. Seed Campaigns
    campaigns = [
        ('Summer Sale 2024', 'Facebook', 50000, 45000, 120000, 150, 12, 'Running'),
        ('Google Search Ads', 'Google', 30000, 28000, 85000, 80, 5, 'Running'),
        ('Instagram Brand Awareness', 'Instagram', 20000, 18000, 40000, 200, 3, 'Paused'),
        ('WhatsApp Lead Gen', 'WhatsApp', 10000, 5000, 25000, 45, 8, 'Running'),
    ]
    
    cursor.execute("DELETE FROM campaigns")
    for name, plat, bud, sp, rev, leads, conv, status in campaigns:
        cursor.execute("""
            INSERT INTO campaigns (name, platform, budget, spend, revenue, leads_generated, conversions, status, organisation_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, plat, bud, sp, rev, leads, conv, status, org_id))
        
    # 2. Seed Expenses
    categories = ['Marketing', 'Employee', 'Software', 'Operational']
    cursor.execute("DELETE FROM expenses")
    for i in range(15):
        cat = random.choice(categories)
        amt = random.randint(1000, 15000)
        dt = date.today() - timedelta(days=random.randint(0, 60))
        cursor.execute("""
            INSERT INTO expenses (title, category, amount, expense_date, organisation_id, added_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (f"Sample {cat} Expense {i}", cat, amt, dt, org_id, user_id))
        
    conn.commit()
    cursor.close()
    conn.close()
    print("Marketing seed data added successfully.")

if __name__ == "__main__":
    seed_marketing_data()
