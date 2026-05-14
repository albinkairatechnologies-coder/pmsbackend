from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.utils.database import get_db_connection
from datetime import date, timedelta
from decimal import Decimal

analytics_bp = Blueprint('analytics', __name__)

LEAD_ROLES = ['admin', 'team_lead', 'crm_head', 'marketing_head']


def _s(row):
    if row is None:
        return None
    out = {}
    for k, v in row.items():
        if isinstance(v, (date,)):
            out[k] = v.isoformat()
        elif isinstance(v, timedelta):
            out[k] = round(v.total_seconds() / 3600, 2)
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


@analytics_bp.route('/analytics/hr', methods=['GET'])
@jwt_required()
def hr_analytics():
    claims = get_jwt()
    if claims['role'] not in LEAD_ROLES:
        return jsonify({'error': 'Unauthorized'}), 403

    # Default: current month
    today = date.today()
    start = request.args.get('start', today.replace(day=1).isoformat())
    end   = request.args.get('end',   today.isoformat())

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ── 1. Attendance overview ────────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(DISTINCT user_id)                          AS total_employees,
            COUNT(*)                                         AS total_records,
            SUM(status = 'present')                          AS present_days,
            SUM(status = 'late')                             AS late_days,
            SUM(status = 'half_day')                         AS half_days,
            SUM(status = 'absent')                           AS absent_days,
            SUM(status = 'on_leave')                         AS on_leave_days,
            ROUND(AVG(net_hours), 2)                         AS avg_net_hours,
            ROUND(AVG(late_by_minutes), 2)                   AS avg_late_minutes
        FROM attendance
        WHERE date BETWEEN %s AND %s
    """, (start, end))
    attendance_overview = _s(cursor.fetchone()) or {}

    # ── 2. Daily attendance trend ─────────────────────────────
    cursor.execute("""
        SELECT
            date,
            COUNT(*)                    AS total,
            SUM(status='present')       AS present,
            SUM(status='late')          AS late,
            SUM(status='absent')        AS absent,
            SUM(status='on_leave')      AS on_leave,
            ROUND(AVG(net_hours), 2)    AS avg_hours
        FROM attendance
        WHERE date BETWEEN %s AND %s
        GROUP BY date
        ORDER BY date ASC
    """, (start, end))
    daily_trend = [_s(r) for r in cursor.fetchall()]

    # ── 3. Per-employee attendance summary ────────────────────
    cursor.execute("""
        SELECT
            u.id, u.name, u.role,
            t.name  AS team_name,
            dp.name AS department_name,
            COUNT(a.id)                          AS total_days,
            SUM(a.status = 'present')            AS present,
            SUM(a.status = 'late')               AS late,
            SUM(a.status = 'absent')             AS absent,
            SUM(a.status = 'on_leave')           AS on_leave,
            ROUND(AVG(a.net_hours), 2)           AS avg_hours,
            ROUND(SUM(a.net_hours), 2)           AS total_hours,
            ROUND(AVG(a.late_by_minutes), 2)     AS avg_late_min
        FROM users u
        LEFT JOIN attendance a  ON u.id = a.user_id AND a.date BETWEEN %s AND %s
        LEFT JOIN teams      t  ON u.team_id = t.id
        LEFT JOIN departments dp ON u.department_id = dp.id
        WHERE u.role NOT IN ('admin', 'client')
        GROUP BY u.id
        ORDER BY total_hours DESC
    """, (start, end))
    employee_attendance = [_s(r) for r in cursor.fetchall()]

    # ── 4. Leave stats ────────────────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(*)                        AS total_requests,
            SUM(status = 'approved')        AS approved,
            SUM(status = 'pending')         AS pending,
            SUM(status = 'rejected')        AS rejected,
            SUM(leave_type = 'sick')        AS sick,
            SUM(leave_type = 'casual')      AS casual,
            SUM(leave_type = 'emergency')   AS emergency,
            SUM(leave_type = 'annual')      AS annual,
            ROUND(AVG(total_days), 1)       AS avg_days
        FROM leave_requests
        WHERE start_date BETWEEN %s AND %s
    """, (start, end))
    leave_stats = _s(cursor.fetchone()) or {}

    # ── 5. Leave by employee ──────────────────────────────────
    cursor.execute("""
        SELECT
            u.name, u.role, t.name AS team_name,
            COUNT(lr.id)                    AS requests,
            SUM(lr.total_days)              AS total_days_taken,
            SUM(lr.status = 'approved')     AS approved,
            SUM(lr.status = 'rejected')     AS rejected
        FROM users u
        LEFT JOIN leave_requests lr ON u.id = lr.user_id AND lr.start_date BETWEEN %s AND %s
        LEFT JOIN teams t ON u.team_id = t.id
        WHERE u.role NOT IN ('admin', 'client')
        GROUP BY u.id
        HAVING requests > 0
        ORDER BY total_days_taken DESC
    """, (start, end))
    leave_by_employee = [_s(r) for r in cursor.fetchall()]

    # ── 6. Activity / productivity ────────────────────────────
    cursor.execute("""
        SELECT
            u.id, u.name, u.role,
            t.name AS team_name,
            ROUND(AVG(es.productivity_score), 1)    AS avg_productivity,
            ROUND(SUM(es.today_active_seconds)/3600, 2) AS total_active_hours
        FROM users u
        LEFT JOIN employee_status es ON u.id = es.user_id
        LEFT JOIN teams t ON u.team_id = t.id
        WHERE u.role NOT IN ('admin', 'client')
        GROUP BY u.id
        ORDER BY avg_productivity DESC
    """)
    productivity = [_s(r) for r in cursor.fetchall()]

    # ── 7. Feedback stats ─────────────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(*)                                AS total,
            ROUND(AVG(rating), 1)                   AS avg_rating,
            SUM(category = 'work_environment')      AS work_environment,
            SUM(category = 'team_issue')            AS team_issue,
            SUM(category = 'suggestion')            AS suggestion,
            SUM(category = 'general')               AS general,
            SUM(visibility = 'anonymous')           AS anonymous_count
        FROM feedback
        WHERE created_at BETWEEN %s AND %s
    """, (start, end))
    feedback_stats = _s(cursor.fetchone()) or {}

    # ── 8. Review meetings summary ────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(*)                            AS total,
            SUM(status = 'completed')           AS completed,
            SUM(status = 'scheduled')           AS scheduled,
            SUM(status = 'cancelled')           AS cancelled,
            ROUND(AVG(rating), 1)               AS avg_rating
        FROM review_meetings
        WHERE meeting_date BETWEEN %s AND %s
    """, (start, end))
    review_stats = _s(cursor.fetchone()) or {}

    # ── 9. Permission stats ───────────────────────────────────
    cursor.execute("""
        SELECT
            COUNT(*)                        AS total,
            SUM(status = 'approved')        AS approved,
            SUM(status = 'pending')         AS pending,
            SUM(status = 'rejected')        AS rejected,
            ROUND(AVG(duration_minutes), 0) AS avg_duration_min
        FROM permission_requests
        WHERE date BETWEEN %s AND %s
    """, (start, end))
    permission_stats = _s(cursor.fetchone()) or {}

    # ── 10. Top late employees ────────────────────────────────
    cursor.execute("""
        SELECT
            u.name, u.role, t.name AS team_name,
            COUNT(*)                            AS late_count,
            ROUND(AVG(a.late_by_minutes), 0)    AS avg_late_min
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        LEFT JOIN teams t ON u.team_id = t.id
        WHERE a.status = 'late' AND a.date BETWEEN %s AND %s
        GROUP BY u.id
        ORDER BY late_count DESC
        LIMIT 10
    """, (start, end))
    top_late = [_s(r) for r in cursor.fetchall()]

    cursor.close(); conn.close()

    return jsonify({
        'period':               {'start': start, 'end': end},
        'attendance_overview':  attendance_overview,
        'daily_trend':          daily_trend,
        'employee_attendance':  employee_attendance,
        'leave_stats':          leave_stats,
        'leave_by_employee':    leave_by_employee,
        'productivity':         productivity,
        'feedback_stats':       feedback_stats,
        'review_stats':         review_stats,
        'permission_stats':     permission_stats,
        'top_late':             top_late,
    }), 200


@analytics_bp.route('/analytics/marketing', methods=['GET'])
@jwt_required()
def marketing_analytics():
    user = get_jwt()
    org_id = user.get('organisation_id')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Campaign Stats
    cursor.execute("""
        SELECT platform, COUNT(*) as count, SUM(budget) as budget, SUM(spend) as spend, 
               SUM(revenue) as revenue, SUM(leads_generated) as leads, SUM(conversions) as conversions
        FROM campaigns WHERE organisation_id = %s OR %s IS NULL
        GROUP BY platform
    """, (org_id, org_id))
    campaign_stats = [_s(r) for r in cursor.fetchall()]

    # 2. Lead Conversion Funnel
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM leads WHERE organisation_id = %s OR %s IS NULL
        GROUP BY status
    """, (org_id, org_id))
    lead_funnel = [_s(r) for r in cursor.fetchall()]

    # 3. Financial Summary
    cursor.execute("""
        SELECT 
            (SELECT COALESCE(SUM(amount), 0) FROM client_payments cp JOIN clients c ON cp.client_id = c.id WHERE c.organisation_id = %s OR %s IS NULL) as revenue,
            (SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE organisation_id = %s OR %s IS NULL) as expenses
    """, (org_id, org_id, org_id, org_id))
    finance_summary = _s(cursor.fetchone())
    
    # 4. Employee-wise Lead Generation
    cursor.execute("""
        SELECT u.name, COUNT(l.id) as leads_count, SUM(l.status = 'converted') as conversions
        FROM users u
        LEFT JOIN leads l ON u.id = l.created_by
        WHERE u.organisation_id = %s OR %s IS NULL
        GROUP BY u.id
        HAVING leads_count > 0
        ORDER BY leads_count DESC
    """, (org_id, org_id))
    employee_performance = [_s(r) for r in cursor.fetchall()]

    # 5. Monthly Trend (Last 6 Months)
    cursor.execute("""
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
            WHERE c.organisation_id = %s OR %s IS NULL
            GROUP BY m
        ) rev ON months.m = rev.m
        LEFT JOIN (
            SELECT DATE_FORMAT(expense_date, '%Y-%m') as m, SUM(amount) as amount
            FROM expenses 
            WHERE organisation_id = %s OR %s IS NULL
            GROUP BY m
        ) exp ON months.m = exp.m
        ORDER BY months.m ASC
    """, (org_id, org_id, org_id, org_id))
    monthly_trend = [_s(r) for r in cursor.fetchall()]

    cursor.close(); conn.close()

    rev = float(finance_summary['revenue'])
    exp = float(finance_summary['expenses'])
    profit = rev - exp
    roi = (profit / exp * 100) if exp > 0 else 0

    return jsonify({
        "campaigns": campaign_stats,
        "leads": lead_funnel,
        "finance": {
            "total_revenue": rev,
            "total_expenses": exp,
            "net_profit": profit,
            "roi_percentage": roi,
            "monthly_trend": monthly_trend
        },
        "employee_performance": employee_performance
    }), 200
