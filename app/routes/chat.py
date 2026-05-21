from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.utils.database import get_db_connection
from datetime import datetime

chat_bp = Blueprint('chat', __name__)


def _require_superadmin():
    claims = get_jwt()
    if not claims.get('is_superadmin'):
        return None, (jsonify({'error': 'Superadmin access required'}), 403)
    return int(get_jwt_identity()), None


def _serialize(row):
    if not row:
        return row
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ── Superadmin: list all org admins with last message + unread count ──
@chat_bp.route('/superadmin/chat/contacts', methods=['GET'])
@jwt_required()
def sa_get_contacts():
    sa_id, err = _require_superadmin()
    if err:
        return err

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all org admins
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.organisation_id,
               o.name as org_name, o.is_active as org_active
        FROM users u
        JOIN organisations o ON u.organisation_id = o.id
        WHERE u.role = 'admin' AND u.organisation_id IS NOT NULL
        ORDER BY o.name, u.name
    """)
    admins = cursor.fetchall()

    for admin in admins:
        # Last message
        cursor.execute("""
            SELECT message, created_at, sender_type
            FROM superadmin_chats
            WHERE organisation_id = %s
            ORDER BY created_at DESC LIMIT 1
        """, (admin['organisation_id'],))
        last = cursor.fetchone()
        admin['last_message'] = _serialize(last)

        # Unread count (messages from admin not read by superadmin)
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM superadmin_chats
            WHERE organisation_id = %s AND sender_type = 'admin' AND is_read = 0
        """, (admin['organisation_id'],))
        admin['unread_count'] = cursor.fetchone()['cnt']

    cursor.close(); conn.close()

    # Sort by latest message
    admins.sort(
        key=lambda a: a['last_message']['created_at'] if a.get('last_message') else '',
        reverse=True
    )
    return jsonify(admins), 200


# ── Superadmin: get messages with a specific org ──
@chat_bp.route('/superadmin/chat/<int:org_id>/messages', methods=['GET'])
@jwt_required()
def sa_get_messages(org_id):
    sa_id, err = _require_superadmin()
    if err:
        return err

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Mark admin messages as read
    cursor.execute("""
        UPDATE superadmin_chats SET is_read = 1
        WHERE organisation_id = %s AND sender_type = 'admin' AND is_read = 0
    """, (org_id,))
    conn.commit()

    cursor.execute("""
        SELECT sc.*,
               CASE WHEN sc.sender_type = 'superadmin' THEN sa.name
                    ELSE u.name END AS sender_name
        FROM superadmin_chats sc
        LEFT JOIN superadmins sa ON sc.sender_type = 'superadmin' AND sc.sender_id = sa.id
        LEFT JOIN users u ON sc.sender_type = 'admin' AND sc.sender_id = u.id
        WHERE sc.organisation_id = %s
        ORDER BY sc.created_at ASC
        LIMIT 100
    """, (org_id,))
    messages = [_serialize(r) for r in cursor.fetchall()]
    cursor.close(); conn.close()
    return jsonify(messages), 200


# ── Superadmin: send message to org ──
@chat_bp.route('/superadmin/chat/<int:org_id>/send', methods=['POST'])
@jwt_required()
def sa_send_message(org_id):
    sa_id, err = _require_superadmin()
    if err:
        return err

    message = (request.get_json() or {}).get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    # Get org admin id
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id FROM users WHERE organisation_id = %s AND role = 'admin' LIMIT 1
    """, (org_id,))
    admin = cursor.fetchone()
    if not admin:
        cursor.close(); conn.close()
        return jsonify({'error': 'No admin found for this organisation'}), 404

    cursor.execute("""
        INSERT INTO superadmin_chats
            (sender_type, sender_id, receiver_type, receiver_id, organisation_id, message)
        VALUES ('superadmin', %s, 'admin', %s, %s, %s)
    """, (sa_id, admin['id'], org_id, message))
    conn.commit()
    msg_id = cursor.lastrowid

    cursor.execute("SELECT * FROM superadmin_chats WHERE id = %s", (msg_id,))
    row = _serialize(cursor.fetchone())
    cursor.close(); conn.close()
    return jsonify(row), 201


# ── Org Admin: get messages with superadmin ──
@chat_bp.route('/admin/chat/messages', methods=['GET'])
@jwt_required()
def admin_get_messages():
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    user_id = int(get_jwt_identity())
    org_id  = claims.get('organisation_id')
    if not org_id:
        return jsonify({'error': 'No organisation assigned'}), 400

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Mark superadmin messages as read
    cursor.execute("""
        UPDATE superadmin_chats SET is_read = 1
        WHERE organisation_id = %s AND sender_type = 'superadmin' AND is_read = 0
    """, (org_id,))
    conn.commit()

    cursor.execute("""
        SELECT sc.*,
               CASE WHEN sc.sender_type = 'superadmin' THEN sa.name
                    ELSE u.name END AS sender_name
        FROM superadmin_chats sc
        LEFT JOIN superadmins sa ON sc.sender_type = 'superadmin' AND sc.sender_id = sa.id
        LEFT JOIN users u ON sc.sender_type = 'admin' AND sc.sender_id = u.id
        WHERE sc.organisation_id = %s
        ORDER BY sc.created_at ASC LIMIT 100
    """, (org_id,))
    messages = [_serialize(r) for r in cursor.fetchall()]
    cursor.close(); conn.close()
    return jsonify(messages), 200


# ── Org Admin: send message to superadmin ──
@chat_bp.route('/admin/chat/send', methods=['POST'])
@jwt_required()
def admin_send_message():
    claims  = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    user_id = int(get_jwt_identity())
    org_id  = claims.get('organisation_id')
    if not org_id:
        return jsonify({'error': 'No organisation assigned'}), 400

    message = (request.get_json() or {}).get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get superadmin id (first active one)
    cursor.execute("SELECT id FROM superadmins WHERE is_active = 1 ORDER BY id LIMIT 1")
    sa = cursor.fetchone()
    if not sa:
        cursor.close(); conn.close()
        return jsonify({'error': 'No superadmin available'}), 404

    cursor.execute("""
        INSERT INTO superadmin_chats
            (sender_type, sender_id, receiver_type, receiver_id, organisation_id, message)
        VALUES ('admin', %s, 'superadmin', %s, %s, %s)
    """, (user_id, sa['id'], org_id, message))
    conn.commit()
    msg_id = cursor.lastrowid

    cursor.execute("SELECT * FROM superadmin_chats WHERE id = %s", (msg_id,))
    row = _serialize(cursor.fetchone())
    cursor.close(); conn.close()
    return jsonify(row), 201


# ── Org Admin: unread count from superadmin ──
@chat_bp.route('/admin/chat/unread', methods=['GET'])
@jwt_required()
def admin_unread_count():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    if not org_id:
        return jsonify({'count': 0}), 200
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) as cnt FROM superadmin_chats
        WHERE organisation_id = %s AND sender_type = 'superadmin' AND is_read = 0
    """, (org_id,))
    cnt = cursor.fetchone()['cnt']
    cursor.close(); conn.close()
    return jsonify({'count': cnt}), 200
