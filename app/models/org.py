from app.utils.database import get_db_connection

class Team:
    @staticmethod
    def create(name, description=None, org_id=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO teams (name, description, organisation_id) VALUES (%s, %s, %s)",
            (name, description, org_id)
        )
        conn.commit()
        team_id = cursor.lastrowid
        cursor.close(); conn.close()
        return team_id

    @staticmethod
    def get_all(org_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        if org_id is not None:
            cursor.execute("""
                SELECT t.*, COUNT(DISTINCT u.id) as member_count
                FROM teams t
                LEFT JOIN users u ON u.team_id = t.id
                WHERE t.organisation_id = %s
                GROUP BY t.id ORDER BY t.created_at ASC
            """, (org_id,))
        else:
            cursor.execute("""
                SELECT t.*, COUNT(DISTINCT u.id) as member_count
                FROM teams t
                LEFT JOIN users u ON u.team_id = t.id
                GROUP BY t.id ORDER BY t.created_at ASC
            """)
        teams = cursor.fetchall()
        cursor.close(); conn.close()
        return teams

    @staticmethod
    def get_by_id(team_id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM teams WHERE id = %s", (team_id,))
        team = cursor.fetchone()
        cursor.close(); conn.close()
        return team

    @staticmethod
    def delete(team_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM teams WHERE id = %s", (team_id,))
        conn.commit()
        cursor.close(); conn.close()


class Department:
    @staticmethod
    def create(name, team_id, description=None):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO departments (name, team_id, description) VALUES (%s, %s, %s)",
            (name, team_id, description)
        )
        conn.commit()
        dept_id = cursor.lastrowid
        cursor.close(); conn.close()
        return dept_id

    @staticmethod
    def get_all(team_id=None, org_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        conditions = []
        params = []

        if team_id:
            conditions.append("d.team_id = %s")
            params.append(team_id)
        if org_id is not None:
            conditions.append("t.organisation_id = %s")
            params.append(org_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor.execute(f"""
            SELECT d.*, t.name as team_name, COUNT(DISTINCT u.id) as member_count
            FROM departments d
            JOIN teams t ON d.team_id = t.id
            LEFT JOIN users u ON u.department_id = d.id
            {where}
            GROUP BY d.id ORDER BY t.id, d.id
        """, params)
        depts = cursor.fetchall()
        cursor.close(); conn.close()
        return depts

    @staticmethod
    def get_by_id(dept_id):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT d.*, t.name as team_name FROM departments d
            JOIN teams t ON d.team_id = t.id WHERE d.id = %s
        """, (dept_id,))
        dept = cursor.fetchone()
        cursor.close(); conn.close()
        return dept

    @staticmethod
    def delete(dept_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM departments WHERE id = %s", (dept_id,))
        conn.commit()
        cursor.close(); conn.close()
