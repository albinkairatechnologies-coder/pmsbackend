from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.utils.database import get_db_connection
from app.models.notification import Notification

announcements_bp = Blueprint('announcements', __name__)


@announcements_bp.route('/announcements', methods=['GET'])
@jwt_required()
def get_announcements():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    org_f  = "AND a.organisation_id = %s" if org_id is not None else ""
    params = ([org_id] if org_id is not None else [])
    cursor.execute(f'''
        SELECT a.*, u.name as sender_name, u.role as sender_role,
               (SELECT COUNT(*) FROM announcement_comments WHERE announcement_id = a.id) as comment_count
        FROM announcements a
        JOIN users u ON a.created_by = u.id
        WHERE 1=1 {org_f}
        ORDER BY a.created_at DESC
    ''', params)
    announcements = cursor.fetchall() or []
    cursor.close(); conn.close()
    return jsonify(announcements), 200


@announcements_bp.route('/announcements', methods=['POST'])
@jwt_required()
def create_announcement():
    user_id = int(get_jwt_identity())
    claims  = get_jwt()
    org_id  = claims.get('organisation_id')
    if claims.get('role') not in ['admin', 'marketing_head', 'crm_head', 'team_lead']:
        return jsonify({'error': 'Only leadership can create announcements'}), 403
    data    = request.get_json()
    title   = data.get('title')
    content = data.get('content')
    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400
    try:
        conn   = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO announcements (title, content, created_by, organisation_id) VALUES (%s, %s, %s, %s)',
            (title, content, user_id, org_id)
        )
        ann_id = cursor.lastrowid
        conn.commit()
        cursor.close(); conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    try:
        conn2   = get_db_connection()
        cursor2 = conn2.cursor()
        org_f   = "AND organisation_id = %s" if org_id is not None else ""
        params  = ([org_id] if org_id is not None else []) + [user_id]
        cursor2.execute(f'SELECT id FROM users WHERE 1=1 {org_f} AND id != %s', params)
        user_ids = [row[0] for row in cursor2.fetchall()]
        cursor2.close(); conn2.close()
    except Exception:
        user_ids = []

    for uid in user_ids:
        try:
            Notification.push(uid, 'announcement', '📢 Official Announcement', f"New announcement: {title}", '/dashboard/announcements')
        except Exception:
            pass

    return jsonify({'message': 'Announcement created', 'id': ann_id}), 201


@announcements_bp.route('/announcements/<int:ann_id>', methods=['PUT', 'DELETE'])
@jwt_required()
def manage_announcement(ann_id):
    claims = get_jwt()
    if claims.get('role') not in ['admin', 'marketing_head', 'crm_head', 'team_lead']:
        return jsonify({'error': 'Unauthorized'}), 403
    conn   = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'DELETE':
        cursor.execute('DELETE FROM announcements WHERE id = %s', (ann_id,))
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'message': 'Announcement deleted'}), 200
    data = request.get_json()
    cursor.execute('UPDATE announcements SET title=%s, content=%s WHERE id=%s', (data.get('title'), data.get('content'), ann_id))
    conn.commit(); cursor.close(); conn.close()
    return jsonify({'message': 'Announcement updated'}), 200


@announcements_bp.route('/announcements/<int:ann_id>/comments', methods=['GET', 'POST'])
@jwt_required()
def manage_comments(ann_id):
    user_id = int(get_jwt_identity())
    conn    = get_db_connection()
    cursor  = conn.cursor(dictionary=True)
    if request.method == 'POST':
        data    = request.get_json()
        content = data.get('content')
        if not content:
            cursor.close(); conn.close()
            return jsonify({'error': 'Comment content required'}), 400
        cursor.execute('INSERT INTO announcement_comments (announcement_id, user_id, content) VALUES (%s,%s,%s)', (ann_id, user_id, content))
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'message': 'Comment added'}), 201
    cursor.execute('''
        SELECT c.*, u.name as user_name, u.role as user_role
        FROM announcement_comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.announcement_id = %s ORDER BY c.created_at ASC
    ''', (ann_id,))
    comments = cursor.fetchall() or []
    cursor.close(); conn.close()
    return jsonify(comments), 200
