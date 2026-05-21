from app.utils.database import get_db_connection


class Organisation:
    @staticmethod
    def create(name, slug, email, phone=None, address=None, plan='trial', trial_ends_at=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO organisations (name, slug, email, phone, address, plan, trial_ends_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (name, slug, email, phone, address, plan, trial_ends_at)
            )
            conn.commit()
            org_id = cursor.lastrowid
            cursor.close()
            return org_id
        finally:
            conn.close()

    @staticmethod
    def get_all():
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT o.*,
                       COUNT(DISTINCT u.id) as user_count
                FROM organisations o
                LEFT JOIN users u ON u.organisation_id = o.id
                GROUP BY o.id
                ORDER BY o.created_at DESC
            """)
            orgs = cursor.fetchall()
            cursor.close()
            return orgs
        finally:
            conn.close()

    @staticmethod
    def get_by_id(org_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT o.*,
                       COUNT(DISTINCT u.id) as user_count
                FROM organisations o
                LEFT JOIN users u ON u.organisation_id = o.id
                WHERE o.id = %s
                GROUP BY o.id
            """, (org_id,))
            org = cursor.fetchone()
            cursor.close()
            return org
        finally:
            conn.close()

    @staticmethod
    def get_by_slug(slug):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM organisations WHERE slug = %s", (slug,))
            org = cursor.fetchone()
            cursor.close()
            return org
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM organisations WHERE email = %s", (email,))
            org = cursor.fetchone()
            cursor.close()
            return org
        finally:
            conn.close()

    @staticmethod
    def update(org_id, **kwargs):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            fields = [f"{k} = %s" for k in kwargs]
            values = list(kwargs.values()) + [org_id]
            cursor.execute(f"UPDATE organisations SET {', '.join(fields)} WHERE id = %s", values)
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def delete(org_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM organisations WHERE id = %s", (org_id,))
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def get_users(org_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.id, u.name, u.email, u.role, u.phone,
                       u.team_id, u.department_id, u.created_at,
                       t.name as team_name, d.name as department_name
                FROM users u
                LEFT JOIN teams t ON u.team_id = t.id
                LEFT JOIN departments d ON u.department_id = d.id
                WHERE u.organisation_id = %s
                ORDER BY u.role, u.name
            """, (org_id,))
            users = cursor.fetchall()
            cursor.close()
            return users
        finally:
            conn.close()
