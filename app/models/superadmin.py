from app.utils.database import get_db_connection
from app.utils.auth import hash_password


class SuperAdmin:
    @staticmethod
    def create(name, email, password):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO superadmins (name, email, password) VALUES (%s, %s, %s)",
                (name, email, hash_password(password))
            )
            conn.commit()
            sa_id = cursor.lastrowid
            cursor.close()
            return sa_id
        finally:
            conn.close()

    @staticmethod
    def get_by_email(email):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM superadmins WHERE email = %s", (email,))
            sa = cursor.fetchone()
            cursor.close()
            return sa
        finally:
            conn.close()

    @staticmethod
    def get_by_id(sa_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, name, email, is_active, created_at FROM superadmins WHERE id = %s",
                (sa_id,)
            )
            sa = cursor.fetchone()
            cursor.close()
            return sa
        finally:
            conn.close()

    @staticmethod
    def log_action(superadmin_id, action, target_type=None, target_id=None, details=None, ip_address=None):
        import json
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO superadmin_audit_logs
                   (superadmin_id, action, target_type, target_id, details, ip_address)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (superadmin_id, action, target_type, target_id,
                 json.dumps(details) if details else None, ip_address)
            )
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def get_audit_logs(limit=100, offset=0):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT al.*, sa.name as superadmin_name, sa.email as superadmin_email
                FROM superadmin_audit_logs al
                JOIN superadmins sa ON al.superadmin_id = sa.id
                ORDER BY al.created_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            logs = cursor.fetchall()
            cursor.close()
            return logs
        finally:
            conn.close()
