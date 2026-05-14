from app.utils.database import get_db_connection

class Expense:
    @staticmethod
    def create(title, category, amount, expense_date, description=None, organisation_id=None, added_by=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expenses (title, category, amount, expense_date, description, organisation_id, added_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (title, category, amount, expense_date, description, organisation_id, added_by))
            conn.commit()
            eid = cursor.lastrowid
            cursor.close()
            return eid
        finally:
            conn.close()

    @staticmethod
    def get_all(organisation_id=None, category=None, start_date=None, end_date=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            query = "SELECT e.*, u.name as added_by_name FROM expenses e LEFT JOIN users u ON e.added_by = u.id WHERE 1=1"
            params = []
            if organisation_id is not None:
                query += " AND e.organisation_id = %s"
                params.append(organisation_id)
            if category:
                query += " AND e.category = %s"
                params.append(category)
            if start_date:
                query += " AND e.expense_date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND e.expense_date <= %s"
                params.append(end_date)
            query += " ORDER BY e.expense_date DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            return rows
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
                    category,
                    SUM(amount) as total_amount
                FROM expenses {where}
                GROUP BY category
            """, params)
            stats = cursor.fetchall()
            cursor.close()
            return stats
        finally:
            conn.close()

    @staticmethod
    def get_monthly_summary(organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            where = "WHERE organisation_id = %s" if organisation_id is not None else ""
            params = (organisation_id,) if organisation_id is not None else ()
            cursor.execute(f"""
                SELECT 
                    DATE_FORMAT(expense_date, '%Y-%m') as month,
                    SUM(amount) as total_amount
                FROM expenses {where}
                GROUP BY month
                ORDER BY month DESC
                LIMIT 12
            """, params)
            summary = cursor.fetchall()
            cursor.close()
            return summary
        finally:
            conn.close()

    @staticmethod
    def delete(expense_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
            conn.commit()
            cursor.close()
        finally:
            conn.close()
