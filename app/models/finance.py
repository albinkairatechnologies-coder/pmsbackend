from app.utils.database import get_db_connection


class ClientPayment:

    @staticmethod
    def add_payment(client_id, amount, payment_date, payment_method, reference, notes, added_by):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO client_payments (client_id, amount, payment_date, payment_method, reference, notes, added_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (client_id, amount, payment_date, payment_method, reference, notes, added_by))
            conn.commit()
            payment_id = cursor.lastrowid
            cursor.close()
            return payment_id
        finally:
            conn.close()

    @staticmethod
    def get_payments_by_client(client_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT cp.*, u.name as added_by_name
                FROM client_payments cp
                LEFT JOIN users u ON cp.added_by = u.id
                WHERE cp.client_id = %s
                ORDER BY cp.payment_date DESC
            """, (client_id,))
            payments = cursor.fetchall()
            cursor.close()
            return payments
        finally:
            conn.close()

    @staticmethod
    def get_client_finance_summary(client_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT c.id, c.company_name, c.contact_person, c.email, c.phone,
                       c.deadline, c.status, c.total_amount,
                       COALESCE(SUM(cp.amount), 0) AS paid_amount
                FROM clients c
                LEFT JOIN client_payments cp ON c.id = cp.client_id
                WHERE c.id = %s GROUP BY c.id
            """, (client_id,))
            row = cursor.fetchone()
            cursor.close()
            if row:
                row['pending_amount'] = float(row['total_amount'] or 0) - float(row['paid_amount'] or 0)
            return row
        finally:
            conn.close()

    @staticmethod
    def get_all_finance_summary(organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            org_f  = "WHERE c.organisation_id = %s" if organisation_id is not None else ""
            params = ([organisation_id] if organisation_id is not None else [])
            cursor.execute(f"""
                SELECT c.id, c.company_name, c.contact_person, c.email, c.phone,
                       c.deadline, c.status, c.total_amount,
                       COALESCE(SUM(cp.amount), 0) AS paid_amount
                FROM clients c
                LEFT JOIN client_payments cp ON c.id = cp.client_id
                {org_f}
                GROUP BY c.id ORDER BY c.created_at DESC
            """, params)
            rows = cursor.fetchall()
            cursor.close()
            for row in rows:
                row['pending_amount'] = float(row['total_amount'] or 0) - float(row['paid_amount'] or 0)
            return rows
        finally:
            conn.close()

    @staticmethod
    def delete_payment(payment_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM client_payments WHERE id = %s", (payment_id,))
            conn.commit()
            cursor.close()
        finally:
            conn.close()

    @staticmethod
    def get_overall_stats(organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            org_f  = "WHERE c.organisation_id = %s" if organisation_id is not None else ""
            params = ([organisation_id] if organisation_id is not None else [])
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(c.total_amount), 0) AS total_contract,
                    COALESCE(SUM(cp_sum.paid), 0) AS total_collected,
                    COALESCE(SUM(c.total_amount), 0) - COALESCE(SUM(cp_sum.paid), 0) AS total_pending,
                    COUNT(DISTINCT CASE
                        WHEN c.deadline < CURDATE()
                        AND COALESCE(cp_sum.paid, 0) < COALESCE(c.total_amount, 0)
                        THEN c.id END) AS overdue_count
                FROM clients c
                LEFT JOIN (
                    SELECT client_id, SUM(amount) AS paid FROM client_payments GROUP BY client_id
                ) cp_sum ON c.id = cp_sum.client_id
                {org_f}
            """, params)
            stats = cursor.fetchone()
            cursor.close()
            return stats
        finally:
            conn.close()
    @staticmethod
    def get_all_payments(client_id=None, start_date=None, end_date=None, organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT cp.*, c.company_name, u.name as added_by_name
                FROM client_payments cp
                JOIN clients c ON cp.client_id = c.id
                LEFT JOIN users u ON cp.added_by = u.id
                WHERE 1=1
            """
            params = []
            if organisation_id is not None:
                query += " AND c.organisation_id = %s"
                params.append(organisation_id)
            if client_id:
                query += " AND cp.client_id = %s"
                params.append(client_id)
            if start_date:
                query += " AND cp.payment_date >= %s"
                params.append(start_date)
            if end_date:
                query += " AND cp.payment_date <= %s"
                params.append(end_date)
            query += " ORDER BY cp.payment_date DESC"
            cursor.execute(query, params)
            payments = cursor.fetchall()
            cursor.close()
            return payments
        finally:
            conn.close()
    @staticmethod
    def get_full_analytics(organisation_id=None):
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            org_f  = "WHERE organisation_id = %s" if organisation_id is not None else ""
            params = ([organisation_id] if organisation_id is not None else [])
            
            # Revenue from payments
            cursor.execute(f"""
                SELECT COALESCE(SUM(amount), 0) as total_revenue
                FROM client_payments cp
                JOIN clients c ON cp.client_id = c.id
                {org_f.replace('organisation_id', 'c.organisation_id')}
            """, params)
            revenue = cursor.fetchone()['total_revenue']

            # Expenses
            cursor.execute(f"""
                SELECT COALESCE(SUM(amount), 0) as total_expenses
                FROM expenses {org_f}
            """, params)
            expenses = cursor.fetchone()['total_expenses']

            # Monthly data for charts
            cursor.execute(f"""
                SELECT 
                    months.m as month,
                    COALESCE(rev.amount, 0) as revenue,
                    COALESCE(exp.amount, 0) as expense
                FROM (
                    SELECT DATE_FORMAT(CURDATE(), '%Y-%m') as m
                    UNION SELECT DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 1 MONTH), '%Y-%m')
                    UNION SELECT DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 2 MONTH), '%Y-%m')
                    UNION SELECT DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 3 MONTH), '%Y-%m')
                    UNION SELECT DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 4 MONTH), '%Y-%m')
                    UNION SELECT DATE_FORMAT(DATE_SUB(CURDATE(), INTERVAL 5 MONTH), '%Y-%m')
                ) months
                LEFT JOIN (
                    SELECT DATE_FORMAT(payment_date, '%Y-%m') as m, SUM(amount) as amount
                    FROM client_payments cp
                    JOIN clients c ON cp.client_id = c.id
                    {org_f.replace('organisation_id', 'c.organisation_id')}
                    GROUP BY m
                ) rev ON months.m = rev.m
                LEFT JOIN (
                    SELECT DATE_FORMAT(expense_date, '%Y-%m') as m, SUM(amount) as amount
                    FROM expenses {org_f}
                    GROUP BY m
                ) exp ON months.m = exp.m
                ORDER BY months.m ASC
            """, params * 3)
            monthly_data = cursor.fetchall()

            cursor.close()
            
            net_profit = float(revenue) - float(expenses)
            roi = (net_profit / float(expenses) * 100) if expenses > 0 else 0

            return {
                "total_revenue": float(revenue),
                "total_expenses": float(expenses),
                "net_profit": net_profit,
                "roi_percentage": roi,
                "monthly_data": monthly_data
            }
        finally:
            conn.close()
