from app.utils.database import get_db_connection
from datetime import datetime, date
from decimal import Decimal
import json

def _s(row):
    if row is None:
        return None
    out = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        elif isinstance(v, (bytes, bytearray)):
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = v.decode('utf-8', errors='replace')
        else:
            out[k] = v
    return out


class Client:
    @staticmethod
    def create(company_name, contact_person, phone, email, package_purchased,
               project_start_date, deadline, notes, user_id=None, total_amount=None, organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clients (company_name, contact_person, phone, email,
                package_purchased, project_start_date, deadline, notes, user_id, total_amount, organisation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (company_name, contact_person, phone, email, package_purchased,
                  project_start_date, deadline, notes, user_id, total_amount or 0, organisation_id))
            conn.commit()
            client_id = cursor.lastrowid
            cursor.close()
            return client_id
        finally:
            conn.close()

    @staticmethod
    def get_by_id(client_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM clients WHERE id = %s", (client_id,))
            client = cursor.fetchone()
            cursor.close()
            return _s(client)
        finally:
            conn.close()

    @staticmethod
    def get_all(status=None, organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            conditions, params = [], []
            if status:
                conditions.append("status = %s")
                params.append(status)
            if organisation_id is not None:
                conditions.append("organisation_id = %s")
                params.append(organisation_id)
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            cursor.execute(f"SELECT * FROM clients {where} ORDER BY created_at DESC", params)
            clients = cursor.fetchall()
            cursor.close()
            return [_s(c) for c in clients]
        finally:
            conn.close()

    @staticmethod
    def get_by_user(user_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM clients WHERE user_id = %s", (user_id,))
            client = cursor.fetchone()
            cursor.close()
            return _s(client)
        finally:
            conn.close()

    @staticmethod
    def update(client_id, **kwargs):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            fields, values = [], []
            for key, value in kwargs.items():
                if value is not None:
                    fields.append(f"{key} = %s")
                    values.append(value)
            values.append(client_id)
            cursor.execute(f"UPDATE clients SET {', '.join(fields)} WHERE id = %s", values)
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def assign_team(client_id, user_ids):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM team_assignments WHERE client_id = %s", (client_id,))
            for user_id in user_ids:
                cursor.execute("INSERT INTO team_assignments (client_id, user_id) VALUES (%s, %s)",
                               (client_id, user_id))
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def get_team(client_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT u.id, u.name, u.email, u.role
                FROM users u
                JOIN team_assignments ta ON u.id = ta.user_id
                WHERE ta.client_id = %s
            """, (client_id,))
            team = cursor.fetchall()
            cursor.close()
            return [_s(t) for t in team]
        finally:
            conn.close()

    @staticmethod
    def search(query, organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            term = f"%{query}%"
            if organisation_id is not None:
                cursor.execute("""
                    SELECT * FROM clients
                    WHERE (company_name LIKE %s OR contact_person LIKE %s OR email LIKE %s)
                    AND organisation_id = %s
                """, (term, term, term, organisation_id))
            else:
                cursor.execute("""
                    SELECT * FROM clients
                    WHERE company_name LIKE %s OR contact_person LIKE %s OR email LIKE %s
                """, (term, term, term))
            clients = cursor.fetchall()
            cursor.close()
            return [_s(c) for c in clients]
        finally:
            conn.close()
