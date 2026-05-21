from app.utils.database import get_db_connection


class Domain:
    @staticmethod
    def get_all(organisation_id=None):
        conn   = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        org_f  = "WHERE d.organisation_id = %s" if organisation_id is not None else ""
        params = ([organisation_id] if organisation_id is not None else [])
        cursor.execute(f"""
            SELECT d.*, c.company_name FROM domains d
            LEFT JOIN clients c ON d.client_id = c.id
            {org_f}
            ORDER BY d.renewal_date ASC
        """, params)
        rows = cursor.fetchall()
        cursor.close(); conn.close()
        for r in rows:
            if r.get('renewal_date'):
                r['renewal_date'] = r['renewal_date'].isoformat()
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat()
        return rows

    @staticmethod
    def create(domain_name, domain_url, client_id, renewal_date, registrar, notes, added_by, organisation_id=None):
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO domains (domain_name, domain_url, client_id, renewal_date, registrar, notes, added_by, organisation_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (domain_name, domain_url, client_id or None, renewal_date, registrar, notes, added_by, organisation_id))
        conn.commit()
        domain_id = cursor.lastrowid
        cursor.close(); conn.close()
        return domain_id

    @staticmethod
    def update(domain_id, **kwargs):
        conn   = get_db_connection()
        cursor = conn.cursor()
        fields = [f"{k} = %s" for k in kwargs]
        values = list(kwargs.values()) + [domain_id]
        cursor.execute(f"UPDATE domains SET {', '.join(fields)} WHERE id = %s", values)
        conn.commit()
        cursor.close(); conn.close()

    @staticmethod
    def delete(domain_id):
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM domains WHERE id = %s", (domain_id,))
        conn.commit()
        cursor.close(); conn.close()
