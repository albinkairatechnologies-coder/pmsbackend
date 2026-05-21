from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.database import get_db_connection
from datetime import datetime
from werkzeug.utils import secure_filename
import os

messages_bp = Blueprint('messages', __name__)

UPLOAD_FOLDER = 'uploads/messages'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@messages_bp.route('/contacts', methods=['GET'])
@jwt_required()
def get_contacts():
    user_id = int(get_jwt_identity())
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    conn   = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    org_f  = "AND u.organisation_id = %s" if org_id is not None else ""
    params = ([org_id, user_id] if org_id is not None else [user_id])
    cursor.execute(f'''
        SELECT u.id, u.name, u.email, u.role, u.profile_image, d.name as department_name, t.name as team_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        LEFT JOIN teams t ON u.team_id = t.id
        WHERE u.id != %s {org_f}
    ''', [user_id] + ([org_id] if org_id is not None else []))
    contacts = cursor.fetchall() or []
    
    from app.routes.auth import PROFILE_UPLOAD_FOLDER
    import os
    for contact in contacts:
        if contact.get('profile_image'):
            try:
                path = os.path.join(PROFILE_UPLOAD_FOLDER, contact['profile_image'])
                if os.path.exists(path):
                    contact['profile_image'] = f"{contact['profile_image']}?t={int(os.path.getmtime(path))}"
            except: pass
    
    # Add individual chat details
    for contact in contacts:
        cursor.execute('''
            SELECT content, timestamp, sender_id, receiver_id, is_read, file_name, is_edited
            FROM messages
            WHERE (sender_id = %s AND receiver_id = %s)
               OR (sender_id = %s AND receiver_id = %s)
            ORDER BY timestamp DESC
            LIMIT 1
        ''', (user_id, contact['id'], contact['id'], user_id))
        contact['last_message'] = cursor.fetchone()
        
        cursor.execute('''
            SELECT COUNT(*) as unread_count
            FROM messages
            WHERE sender_id = %s AND receiver_id = %s AND is_read = 0 AND group_id IS NULL
        ''', (contact['id'], user_id))
        unread = cursor.fetchone()
        contact['unread_count'] = unread['unread_count'] if unread else 0
        contact['is_group'] = False

    # Get user groups
    cursor.execute('''
        SELECT g.id, g.name, g.created_by, g.created_at
        FROM chat_groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = %s
    ''', (user_id,))
    groups = cursor.fetchall() or []
    
    for g in groups:
        cursor.execute('''
            SELECT m.content, m.timestamp, m.sender_id, u.name as sender_name, m.file_name, m.is_edited
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id = %s
            ORDER BY m.timestamp DESC
            LIMIT 1
        ''', (g['id'],))
        last_msg = cursor.fetchone()
        g['last_message'] = last_msg
        g['is_group'] = True
        g['unread_count'] = 0 # Group unread logic simplified

    cursor.close(); conn.close()

    all_contacts = contacts + groups
    # Sort by latest message timestamp descending — contacts with no messages go to bottom
    all_contacts.sort(
        key=lambda c: c['last_message']['timestamp'].isoformat() if c.get('last_message') and c['last_message'].get('timestamp') else '',
        reverse=True
    )
    return jsonify(all_contacts), 200

@messages_bp.route('/<int:other_user_id>', methods=['GET'])
@jwt_required()
def get_messages(other_user_id):
    user_id = int(get_jwt_identity())
    is_group = request.args.get('is_group') == 'true'
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if is_group:
        cursor.execute('''
            SELECT m.id, m.sender_id, m.group_id, m.content, m.timestamp, m.is_read, m.file_url, m.file_name, m.file_type, m.is_edited, u.name as sender_name, u.profile_image as sender_image
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.group_id = %s
            ORDER BY m.timestamp ASC
        ''', (other_user_id,))
        messages = cursor.fetchall() or []
        from app.routes.auth import PROFILE_UPLOAD_FOLDER
        import os
        for m in messages:
            if m.get('sender_image'):
                try:
                    path = os.path.join(PROFILE_UPLOAD_FOLDER, m['sender_image'])
                    if os.path.exists(path):
                        m['sender_image'] = f"{m['sender_image']}?t={int(os.path.getmtime(path))}"
                except: pass
        cursor.close(); conn.close()
        return jsonify(messages), 200
    else:
        # Mark individual messages as read
        cursor.execute('''
            UPDATE messages
            SET is_read = 1
            WHERE sender_id = %s AND receiver_id = %s AND is_read = 0 AND group_id IS NULL
        ''', (other_user_id, user_id))
        conn.commit()
        
        cursor.execute('''
            SELECT m.id, m.sender_id, m.receiver_id, m.content, m.timestamp, m.is_read, m.file_url, m.file_name, m.file_type, m.is_edited
            FROM messages m
            WHERE (m.sender_id = %s AND m.receiver_id = %s AND m.group_id IS NULL)
               OR (m.sender_id = %s AND m.receiver_id = %s AND m.group_id IS NULL)
            ORDER BY m.timestamp ASC
        ''', (user_id, other_user_id, other_user_id, user_id))
    
    messages = cursor.fetchall() or []
    cursor.close(); conn.close()
    return jsonify(messages), 200

@messages_bp.route('', methods=['POST'])
@jwt_required()
def send_message():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    group_id = data.get('group_id')
    content = data.get('content')
    file_url = data.get('file_url')
    file_name = data.get('file_name')
    file_type = data.get('file_type')
    
    if not receiver_id and not group_id:
        return jsonify({'error': 'recipient (user or group) is required'}), 400
    if not content and not file_url:
        return jsonify({'error': 'content or file is required'}), 400

    # Ensure correct NULL handling: group messages have no receiver, DMs have no group
    db_receiver_id = int(receiver_id) if receiver_id else None
    db_group_id    = int(group_id)    if group_id    else None

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('''
            INSERT INTO messages (sender_id, receiver_id, group_id, content, timestamp, file_url, file_name, file_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (user_id, db_receiver_id, db_group_id, content or '', datetime.now(), file_url, file_name, file_type))
        conn.commit()
        msg_id = cursor.lastrowid

        # --- Trigger Push Notification ---
        try:
            from app.models.notification import Notification
            
            # Get sender name
            cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
            sender_row = cursor.fetchone()
            sender_name = sender_row['name'] if sender_row else 'Someone'
            
            notify_content = content if content else (f"Sent an attachment: {file_name}" if file_name else "Sent a file")
            if len(notify_content) > 60:
                notify_content = notify_content[:57] + "..."
                
            if db_receiver_id:
                # Direct Message
                Notification.push(
                    user_id=db_receiver_id,
                    type="chat_message",
                    title=f"💬 New message from {sender_name}",
                    message=notify_content,
                    link="/dashboard/chat"
                )
            elif db_group_id:
                # Group Message
                cursor.execute("SELECT name FROM chat_groups WHERE id = %s", (db_group_id,))
                group_row = cursor.fetchone()
                group_name = group_row['name'] if group_row else 'Group'
                
                cursor.execute("SELECT user_id FROM group_members WHERE group_id = %s AND user_id != %s", (db_group_id, user_id))
                members = cursor.fetchall()
                for m in members:
                    Notification.push(
                        user_id=m['user_id'],
                        type="group_message",
                        title=f"👥 {group_name}: {sender_name}",
                        message=notify_content,
                        link="/dashboard/chat"
                    )
        except Exception as ex:
            print(f"[Chat Notify Error] Failed to push notification: {ex}")

        cursor.close(); conn.close()
        return jsonify({'message': 'Message sent', 'id': msg_id}), 201
    except Exception as e:
        conn.rollback(); cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/groups', methods=['POST'])
@jwt_required()
def create_group():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    name = data.get('name')
    member_ids = data.get('member_ids', [])
    
    if not name or not member_ids:
        return jsonify({'error': 'group name and members are required'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO chat_groups (name, created_by) VALUES (%s, %s)', (name, user_id))
        group_id = cursor.lastrowid
        
        # Add creator as member
        if user_id not in member_ids: member_ids.append(user_id)
        
        for mid in member_ids:
            cursor.execute('INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)', (group_id, mid))
            
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'message': 'Group created', 'id': group_id}), 201
    except Exception as e:
        conn.rollback(); cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/groups/<int:group_id>/members', methods=['POST'])
@jwt_required()
def add_group_members(group_id):
    data = request.get_json()
    member_ids = data.get('member_ids', [])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for mid in member_ids:
            cursor.execute('INSERT IGNORE INTO group_members (group_id, user_id) VALUES (%s, %s)', (group_id, mid))
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'message': 'Members added'}), 200
    except Exception as e:
        conn.rollback(); cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/groups/<int:group_id>/members', methods=['GET'])
@jwt_required()
def get_group_members(group_id):
    user_id = int(get_jwt_identity())
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Verify group exists
        cursor.execute("SELECT id, name, created_by, created_at FROM chat_groups WHERE id = %s", (group_id,))
        group = cursor.fetchone()
        if not group:
            cursor.close(); conn.close()
            return jsonify({'error': 'Group not found'}), 404
            
        # Verify current user is a member of the group
        cursor.execute("SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, user_id))
        is_member = cursor.fetchone()
        if not is_member:
            cursor.close(); conn.close()
            return jsonify({'error': 'Access denied: not a group member'}), 403
            
        # Get all members details
        cursor.execute("""
            SELECT u.id, u.name, u.email, u.role, u.profile_image, d.name as department_name, t.name as team_name
            FROM users u
            JOIN group_members gm ON u.id = gm.user_id
            LEFT JOIN departments d ON u.department_id = d.id
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE gm.group_id = %s
            ORDER BY u.name
        """, (group_id,))
        members = cursor.fetchall() or []
        
        # Serialize profile images
        from app.routes.auth import PROFILE_UPLOAD_FOLDER
        import os
        for m in members:
            if m.get('profile_image'):
                try:
                    path = os.path.join(PROFILE_UPLOAD_FOLDER, m['profile_image'])
                    if os.path.exists(path):
                        m['profile_image'] = f"{m['profile_image']}?t={int(os.path.getmtime(path))}"
                except: pass
                
        cursor.close(); conn.close()
        return jsonify({
            'group': group,
            'members': members
        }), 200
    except Exception as e:
        cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/groups/<int:group_id>/members/<int:target_user_id>', methods=['DELETE'])
@jwt_required()
def remove_group_member(group_id, target_user_id):
    current_user_id = int(get_jwt_identity())
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    current_user_role = claims.get('role')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Check if group exists and who created it
        cursor.execute("SELECT created_by, name FROM chat_groups WHERE id = %s", (group_id,))
        group = cursor.fetchone()
        if not group:
            cursor.close(); conn.close()
            return jsonify({'error': 'Group not found'}), 404
            
        # Permission check:
        # Allowed if: current user is admin, or current user is the group creator, or current user is leaving the group themselves
        is_creator = (group['created_by'] == current_user_id)
        is_admin = (current_user_role == 'admin')
        is_self_leaving = (target_user_id == current_user_id)
        
        if not (is_creator or is_admin or is_self_leaving):
            cursor.close(); conn.close()
            return jsonify({'error': 'Unauthorized to remove this member'}), 403
            
        # Delete from group_members
        cursor.execute("DELETE FROM group_members WHERE group_id = %s AND user_id = %s", (group_id, target_user_id))
        conn.commit()
        
        cursor.close(); conn.close()
        return jsonify({'message': 'Member removed successfully'}), 200
    except Exception as e:
        conn.rollback(); cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/<int:message_id>', methods=['PUT'])
@jwt_required()
def edit_message(message_id):
    user_id = int(get_jwt_identity())
    data = request.get_json()
    new_content = data.get('content')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT sender_id FROM messages WHERE id = %s', (message_id,))
    msg = cursor.fetchone()
    if not msg or msg[0] != user_id:
        cursor.close(); conn.close()
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        cursor.execute('UPDATE messages SET content = %s, is_edited = 1 WHERE id = %s', (new_content, message_id))
        conn.commit(); cursor.close(); conn.close()
        return jsonify({'message': 'Message updated'}), 200
    except Exception as e:
        conn.rollback(); cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_chat_file():
    if 'file' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    
    # Check file size (e.g. 20MB limit)
    try:
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        MAX_SIZE = 20 * 1024 * 1024 # 20 MB
        if size > MAX_SIZE:
            return jsonify({'error': 'File exceeds maximum limit of 20MB'}), 400
    except Exception as e:
        print(f"[Upload Size Check Error] {e}")

    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return jsonify({'file_url': filename, 'file_name': file.filename, 'file_type': file.content_type}), 201

@messages_bp.route('/attachments/<filename>')
@jwt_required()
def download_chat_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


@messages_bp.route('/delete/<int:message_id>', methods=['DELETE'])
@jwt_required()
def delete_message(message_id):
    user_id = int(get_jwt_identity())
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute('SELECT sender_id FROM messages WHERE id = %s', (message_id,))
        msg = cursor.fetchone()
        if not msg:
            cursor.close(); conn.close()
            return jsonify({'error': 'Message not found'}), 404
        if claims['role'] != 'admin' and msg['sender_id'] != user_id:
            cursor.close(); conn.close()
            return jsonify({'error': 'Unauthorized to delete this message'}), 403
        cursor.execute('DELETE FROM messages WHERE id = %s', (message_id,))
        conn.commit()
        cursor.close(); conn.close()
        return jsonify({'message': 'Message deleted'}), 200
    except Exception as e:
        conn.rollback(); cursor.close(); conn.close()
        return jsonify({'error': str(e)}), 500
