from app.utils.database import get_db_connection
from datetime import datetime, date, timedelta, time
from decimal import Decimal
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')

def _now():
    return datetime.now(IST).replace(tzinfo=None)

def _today():
    return datetime.now(IST).date()

def _s(row):
    if row is None:
        return None
    out = {}
    for k, v in row.items():
        if isinstance(v, timedelta):
            total = int(v.total_seconds())
            out[k] = f"{total // 3600:02d}:{(total % 3600) // 60:02d}"
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


class Attendance:

    @staticmethod
    def check_in(user_id: int, notes: str = None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today = _today()
        now   = _now()
        cursor.execute("SELECT work_start_time, late_threshold_min FROM company_settings WHERE id = 1")
        settings   = cursor.fetchone() or {}
        work_start = settings.get('work_start_time')
        threshold  = settings.get('late_threshold_min', 15)
        if isinstance(work_start, timedelta):
            total_sec  = int(work_start.total_seconds())
            work_start = time(total_sec // 3600, (total_sec % 3600) // 60)
        elif work_start is None:
            work_start = time(9, 0)
        scheduled_dt = datetime.combine(today, work_start)
        diff_minutes = (now - scheduled_dt).total_seconds() / 60
        late_by      = max(0, int(diff_minutes))
        status       = 'late' if diff_minutes > threshold else 'present'
        try:
            cursor.execute("""
                INSERT INTO attendance (user_id, date, check_in_time, status, late_by_minutes, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    check_in_time   = VALUES(check_in_time),
                    status          = VALUES(status),
                    late_by_minutes = VALUES(late_by_minutes),
                    check_out_time  = NULL,
                    total_hours     = NULL,
                    net_hours       = NULL
            """, (user_id, today, now, status, late_by, notes))
            conn.commit()
            cursor.execute("SELECT * FROM attendance WHERE user_id=%s AND date=%s", (user_id, today))
            return _s(cursor.fetchone())
        finally:
            cursor.close(); conn.close()

    @staticmethod
    def check_out(user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today = _today()
        now   = _now()
        cursor.execute("SELECT * FROM attendance WHERE user_id=%s AND date=%s", (user_id, today))
        att = cursor.fetchone()
        if not att or not att['check_in_time']:
            cursor.close(); conn.close()
            return None, "No check-in found for today"
        
        # User can check out again (overwrite last checkout), so we don't block if check_out_time exists.
        check_in = att['check_in_time']
        if isinstance(check_in, str):
            check_in = datetime.fromisoformat(check_in)
        cursor.execute("""
            SELECT COALESCE(SUM(duration_minutes), 0) as total_break
            FROM breaks WHERE user_id=%s AND attendance_id=%s AND status='completed'
        """, (user_id, att['id']))
        break_row     = cursor.fetchone()
        break_minutes = int(break_row['total_break']) if break_row else 0
        total_seconds = (now - check_in).total_seconds()
        total_hours   = round(total_seconds / 3600, 2)
        net_hours     = round(max(0, total_seconds - break_minutes * 60) / 3600, 2)
        status        = att['status']
        if net_hours < 4:
            status = 'half_day'
        cursor.execute("""
            UPDATE attendance
            SET check_out_time=%s, total_hours=%s, break_minutes=%s, net_hours=%s, status=%s
            WHERE id=%s
        """, (now, total_hours, break_minutes, net_hours, status, att['id']))
        conn.commit()
        cursor.execute("SELECT * FROM attendance WHERE id=%s", (att['id'],))
        row = _s(cursor.fetchone())
        cursor.close(); conn.close()
        return row, None

    @staticmethod
    def get_today(user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM attendance WHERE user_id=%s AND date=%s", (user_id, _today()))
        row = _s(cursor.fetchone())
        cursor.close(); conn.close()
        return row

    @staticmethod
    def get_by_user(user_id: int, month: str = None, year: str = None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query  = "SELECT * FROM attendance WHERE user_id=%s"
        params = [user_id]
        if month and year:
            query += " AND MONTH(date)=%s AND YEAR(date)=%s"
            params += [month, year]
        query += " ORDER BY date DESC"
        cursor.execute(query, params)
        rows = [_s(r) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return rows

    @staticmethod
    def get_all_for_date(target_date: str = None, organisation_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        d = target_date or _today().isoformat()
        org_f  = "AND u.organisation_id = %s" if organisation_id is not None else ""
        params = [d] + ([organisation_id] if organisation_id is not None else [])
        cursor.execute(f"""
            SELECT a.*, u.name, u.role,
                   t.name AS team_name, dp.name AS department_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            LEFT JOIN teams t ON u.team_id = t.id
            LEFT JOIN departments dp ON u.department_id = dp.id
            WHERE a.date = %s {org_f}
            ORDER BY a.check_in_time ASC
        """, params)
        rows = [_s(r) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return rows

    @staticmethod
    def get_absent_today(organisation_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today  = _today()
        org_f  = "AND u.organisation_id = %s" if organisation_id is not None else ""
        params = ([organisation_id] if organisation_id is not None else []) + [today]
        cursor.execute(f"""
            SELECT u.id, u.name, u.role,
                   t.name AS team_name, dp.name AS department_name
            FROM users u
            LEFT JOIN teams t ON u.team_id = t.id
            LEFT JOIN departments dp ON u.department_id = dp.id
            WHERE u.role NOT IN ('admin','client') {org_f}
              AND u.id NOT IN (SELECT user_id FROM attendance WHERE date = %s)
            ORDER BY u.name
        """, params)
        rows = [_s(r) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return rows

    @staticmethod
    def get_report(start_date: str, end_date: str, user_id=None, dept_id=None, organisation_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        org_f  = "AND u.organisation_id = %s" if organisation_id is not None else ""
        params = [start_date, end_date] + ([organisation_id] if organisation_id is not None else [])
        query  = f"""
            SELECT a.*, u.name, u.role,
                   t.name AS team_name, dp.name AS department_name
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            LEFT JOIN teams t ON u.team_id = t.id
            LEFT JOIN departments dp ON u.department_id = dp.id
            WHERE a.date BETWEEN %s AND %s {org_f}
        """
        if user_id:
            query += " AND a.user_id=%s"; params.append(user_id)
        if dept_id:
            query += " AND u.department_id=%s"; params.append(dept_id)
        query += " ORDER BY a.date DESC, u.name"
        cursor.execute(query, params)
        rows = [_s(r) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return rows

    @staticmethod
    def get_today_stats(organisation_id=None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        today = _today()
        cursor.execute("""
            SELECT COUNT(*) AS total_present,
                   SUM(status='late') AS total_late,
                   SUM(status='half_day') AS total_half_day,
                   ROUND(AVG(net_hours),2) AS avg_hours,
                   SUM(check_out_time IS NOT NULL) AS checked_out,
                   SUM(check_out_time IS NULL) AS still_working
            FROM attendance WHERE date=%s
        """, (today,))
        stats  = _s(cursor.fetchone()) or {}
        org_f  = "AND organisation_id = %s" if organisation_id is not None else ""
        params = ([organisation_id] if organisation_id is not None else [])
        cursor.execute(f"SELECT COUNT(*) AS total FROM users WHERE role NOT IN ('admin','client') {org_f}", params)
        total_row = cursor.fetchone()
        stats['total_employees'] = total_row['total'] if total_row else 0
        stats['total_absent']    = stats['total_employees'] - (stats.get('total_present') or 0)
        cursor.close(); conn.close()
        return stats


class Break:

    @staticmethod
    def start(user_id: int, break_type: str):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM attendance WHERE user_id=%s AND date=%s", (user_id, _today()))
        att = cursor.fetchone()
        if not att:
            cursor.close(); conn.close()
            return None, "Check in first"
        att_id = att['id']
        cursor.execute("SELECT id FROM breaks WHERE user_id=%s AND attendance_id=%s AND status='active'", (user_id, att_id))
        if cursor.fetchone():
            cursor.close(); conn.close()
            return None, "A break is already active"
        if break_type == 'lunch':
            cursor.execute("SELECT id FROM breaks WHERE user_id=%s AND attendance_id=%s AND break_type='lunch'", (user_id, att_id))
            if cursor.fetchone():
                cursor.close(); conn.close()
                return None, "Lunch break already taken today"
        cursor.execute("INSERT INTO breaks (user_id, attendance_id, break_type, break_start) VALUES (%s,%s,%s,%s)", (user_id, att_id, break_type, _now()))
        conn.commit()
        break_id = cursor.lastrowid
        cursor.execute("SELECT * FROM breaks WHERE id=%s", (break_id,))
        row = _s(cursor.fetchone())
        cursor.close(); conn.close()
        return row, None

    @staticmethod
    def end(user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM attendance WHERE user_id=%s AND date=%s", (user_id, _today()))
        att = cursor.fetchone()
        if not att:
            cursor.close(); conn.close()
            return None, "No attendance record"
        cursor.execute("SELECT * FROM breaks WHERE user_id=%s AND attendance_id=%s AND status='active' ORDER BY break_start DESC LIMIT 1", (user_id, att['id']))
        brk = cursor.fetchone()
        if not brk:
            cursor.close(); conn.close()
            return None, "No active break"
        now      = _now()
        start_dt = brk['break_start']
        if isinstance(start_dt, str):
            start_dt = datetime.fromisoformat(start_dt)
        duration = max(1, int((now - start_dt).total_seconds() / 60))
        cursor.execute("UPDATE breaks SET break_end=%s, duration_minutes=%s, status='completed' WHERE id=%s", (now, duration, brk['id']))
        conn.commit()
        cursor.execute("SELECT * FROM breaks WHERE id=%s", (brk['id'],))
        row = _s(cursor.fetchone())
        cursor.close(); conn.close()
        return row, None

    @staticmethod
    def get_today(user_id: int):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT b.* FROM breaks b
            JOIN attendance a ON b.attendance_id = a.id
            WHERE b.user_id=%s AND a.date=%s ORDER BY b.break_start
        """, (user_id, _today()))
        rows = [_s(r) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return rows

    @staticmethod
    def get_all_for_date(target_date: str = None):
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        d = target_date or _today().isoformat()
        cursor.execute("""
            SELECT b.*, u.name AS user_name FROM breaks b
            JOIN attendance a ON b.attendance_id = a.id
            JOIN users u ON b.user_id = u.id
            WHERE a.date=%s ORDER BY b.break_start
        """, (d,))
        rows = [_s(r) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        return rows
