from app.utils.database import get_db_connection

class Campaign:
    @staticmethod
    def create(name, platform, budget, start_date=None, end_date=None, organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO campaigns (name, platform, budget, start_date, end_date, organisation_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, platform, budget, start_date, end_date, organisation_id))
            conn.commit()
            cid = cursor.lastrowid
            cursor.close()
            return cid
        finally:
            conn.close()

    @staticmethod
    def get_all(organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            where = "WHERE organisation_id = %s" if organisation_id is not None else ""
            params = (organisation_id,) if organisation_id is not None else ()
            cursor.execute(f"SELECT * FROM campaigns {where} ORDER BY created_at DESC", params)
            rows = cursor.fetchall()
            cursor.close()
            return rows
        finally:
            conn.close()

    @staticmethod
    def get_by_id(campaign_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM campaigns WHERE id = %s", (campaign_id,))
            row = cursor.fetchone()
            cursor.close()
            return row
        finally:
            conn.close()

    @staticmethod
    def update(campaign_id, **kwargs):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            fields, values = [], []
            for key, value in kwargs.items():
                fields.append(f"{key} = %s")
                values.append(value)
            values.append(campaign_id)
            cursor.execute(f"UPDATE campaigns SET {', '.join(fields)} WHERE id = %s", values)
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def delete(campaign_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM campaigns WHERE id = %s", (campaign_id,))
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def get_stats(organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            where = "WHERE organisation_id = %s" if organisation_id is not None else ""
            params = (organisation_id,) if organisation_id is not None else ()
            cursor.execute(f"""
                SELECT 
                    platform,
                    COUNT(*) as campaign_count,
                    SUM(budget) as total_budget,
                    SUM(spend) as total_spend,
                    SUM(revenue) as total_revenue,
                    SUM(leads_generated) as total_leads,
                    SUM(conversions) as total_conversions
                FROM campaigns {where}
                GROUP BY platform
            """, params)
            stats = cursor.fetchall()
            cursor.close()
            return stats
        finally:
            conn.close()
