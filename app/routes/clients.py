from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.client import Client
from app.models.user import User
from app.models.other import Notification
from app.models.task import Task
from app.utils.redis import cache

client_bp = Blueprint('client', __name__)

ALLOWED_ROLES = ['admin', 'bdm', 'crm_head', 'marketing_head', 'team_lead']

@client_bp.route('/clients', methods=['POST'])
@jwt_required()
def create_client():
    data = request.json
    claims = get_jwt()
    org_id = claims.get('organisation_id')

    if claims['role'] not in ALLOWED_ROLES:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        user_id = None
        if data.get('email'):
            existing = User.get_by_email(data['email'])
            if existing:
                user_id = existing['id']
            else:
                user_id = User.create(
                    name=data['contact_person'],
                    email=data['email'],
                    password='client123',
                    role='client',
                    phone=data.get('phone'),
                    organisation_id=org_id
                )

        client_id = Client.create(
            company_name=data['company_name'],
            contact_person=data['contact_person'],
            phone=data.get('phone'),
            email=data.get('email'),
            package_purchased=data.get('package_purchased'),
            project_start_date=data.get('project_start_date'),
            deadline=data.get('deadline'),
            notes=data.get('notes'),
            user_id=user_id,
            total_amount=data.get('total_amount'),
            organisation_id=org_id
        )

        if data.get('team_members'):
            Client.assign_team(client_id, data['team_members'])
            for member_id in data['team_members']:
                Notification.create(
                    member_id,
                    "New Client Assignment",
                    f"You have been assigned to {data['company_name']}",
                    "assignment"
                )

        if org_id:
            cache.delete_pattern(f"clients:org_{org_id}:*")
            cache.delete_pattern(f"clients_search:org_{org_id}:*")

        return jsonify({"message": "Client created", "client_id": client_id}), 201
    except Exception as e:
        import traceback
        print(f"[CREATE CLIENT ERROR] {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


@client_bp.route('/clients', methods=['GET'])
@jwt_required()
def get_clients():
    user_id = int(get_jwt_identity())
    claims  = get_jwt()
    org_id  = claims.get('organisation_id')
    status  = request.args.get('status')

    if claims['role'] == 'client':
        cache_key = f"client_user:{user_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return jsonify(cached), 200

        client = Client.get_by_user(user_id)
        if client:
            client['tasks'] = Task.get_by_client(client['id'])
        res = [client] if client else []
        cache.set(cache_key, res, timeout=10)
        return jsonify(res), 200

    cache_key = f"clients:org_{org_id}:status_{status}"
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    clients = Client.get_all(status, organisation_id=org_id)
    for c in clients:
        c['tasks'] = Task.get_by_client(c['id'])
    cache.set(cache_key, clients, timeout=10)
    return jsonify(clients), 200


@client_bp.route('/clients/<int:client_id>', methods=['GET'])
@jwt_required()
def get_client(client_id):
    cache_key = f"client:id_{client_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    client = Client.get_by_id(client_id)
    if not client:
        return jsonify({"error": "Client not found"}), 404
    team = Client.get_team(client_id)
    client['team'] = team
    client['tasks'] = Task.get_by_client(client_id)
    cache.set(cache_key, client, timeout=10)
    return jsonify(client), 200


@client_bp.route('/clients/<int:client_id>', methods=['PUT'])
@jwt_required()
def update_client(client_id):
    data = request.json
    claims = get_jwt()
    if claims['role'] not in ALLOWED_ROLES:
        return jsonify({"error": "Unauthorized"}), 403
    try:
        client = Client.get_by_id(client_id)
        org_id = claims.get('organisation_id')

        Client.update(client_id, **data)
        if data.get('team_members'):
            Client.assign_team(client_id, data['team_members'])

        cache.delete(f"client:id_{client_id}")
        if org_id:
            cache.delete_pattern(f"clients:org_{org_id}:*")
            cache.delete_pattern(f"clients_search:org_{org_id}:*")
        if client and client.get('user_id'):
            cache.delete(f"client_user:{client['user_id']}")

        return jsonify({"message": "Client updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@client_bp.route('/clients/search', methods=['GET'])
@jwt_required()
def search_clients():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    query  = request.args.get('q', '')

    cache_key = f"clients_search:org_{org_id}:q_{query}"
    cached = cache.get(cache_key)
    if cached is not None:
        return jsonify(cached), 200

    clients = Client.search(query, organisation_id=org_id)
    for c in clients:
        c['tasks'] = Task.get_by_client(c['id'])
    cache.set(cache_key, clients, timeout=10)
    return jsonify(clients), 200


def serialize(row):
    if row is None:
        return None
    from datetime import datetime, date
    from decimal import Decimal
    out = {}
    for k, v in row.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out


# ── Public Passwordless Client Tracking Portal Endpoints ───────────────────────

@client_bp.route('/public/clients/track/<string:client_token>', methods=['GET'])
def get_public_tracking_client(client_token):
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM clients WHERE tracking_token = %s LIMIT 1", (client_token,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found or tracking link is invalid."}), 404
        
        serialized_client = serialize(client)
        
        # Get tasks for this client
        tasks = Task.get_by_client(client['id'])
        serialized_client['tasks'] = [serialize(t) for t in tasks]
        
        return jsonify(serialized_client), 200
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error fetching tracking client: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cursor.close(); conn.close()


@client_bp.route('/public/clients/track/<string:client_token>/tasks/<int:task_id>', methods=['GET'])
def get_public_tracking_task(client_token, task_id):
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM clients WHERE tracking_token = %s LIMIT 1", (client_token,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found or tracking link is invalid."}), 404
            
        cursor.execute("""
            SELECT t.*,
                   u.name as assigned_name, u.role as assigned_role,
                   ab.name as assigned_by_name,
                   c.company_name, c.contact_person, c.phone as client_phone, c.email as client_email,
                   tm.name as team_name,
                   d.name as department_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            LEFT JOIN users ab ON t.assigned_by = ab.id
            LEFT JOIN clients c ON t.client_id = c.id
            LEFT JOIN teams tm ON t.team_id = tm.id
            LEFT JOIN departments d ON t.department_id = d.id
            WHERE t.id = %s AND t.client_id = %s
            LIMIT 1
        """, (task_id, client['id']))
        task = cursor.fetchone()
        if not task:
            return jsonify({"error": "Task not found"}), 404
            
        serialized = serialize(task)
        serialized['pipeline_stages'] = Task.get_pipeline_stages(task['id'])
        
        cursor.execute("""
            SELECT action, new_value, created_at
            FROM task_activity
            WHERE task_id = %s
            ORDER BY created_at DESC
        """, (task['id'],))
        activity_logs = cursor.fetchall()
        serialized['activity'] = [serialize(log) for log in activity_logs]
        
        return jsonify(serialized), 200
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error fetching tracking task: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cursor.close(); conn.close()


@client_bp.route('/public/clients/track/<string:client_token>/tasks/<int:task_id>/messages', methods=['GET'])
def get_public_tracking_messages(client_token, task_id):
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM clients WHERE tracking_token = %s LIMIT 1", (client_token,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found or tracking link is invalid."}), 404
            
        # Verify task belongs to client
        cursor.execute("SELECT id FROM tasks WHERE id = %s AND client_id = %s LIMIT 1", (task_id, client['id']))
        task = cursor.fetchone()
        if not task:
            return jsonify({"error": "Unauthorized or task not found"}), 403
            
        messages = Task.get_messages(task_id)
        return jsonify([serialize(m) for m in messages]), 200
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error fetching tracking messages: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cursor.close(); conn.close()


@client_bp.route('/public/clients/track/<string:client_token>/tasks/<int:task_id>/messages', methods=['POST'])
def send_public_tracking_message(client_token, task_id):
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, user_id FROM clients WHERE tracking_token = %s LIMIT 1", (client_token,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found or tracking link is invalid."}), 404
            
        # Verify task belongs to client
        cursor.execute("SELECT id FROM tasks WHERE id = %s AND client_id = %s LIMIT 1", (task_id, client['id']))
        task = cursor.fetchone()
        if not task:
            return jsonify({"error": "Unauthorized or task not found"}), 403
            
        user_id = client.get('user_id')
        if not user_id:
            return jsonify({"error": "No user account associated with this client. Please contact PM."}), 400
            
        data = request.json
        msg_id = Task.send_message(
            task_id=task_id,
            user_id=user_id,
            content=data['content'],
            message_type=data.get('message_type', 'text'),
            file_url=data.get('file_url')
        )
        return jsonify({"message": "Message sent", "id": msg_id}), 201
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error sending tracking message: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cursor.close(); conn.close()


@client_bp.route('/public/clients/track/<string:client_token>/tasks/<int:task_id>/upload', methods=['POST'])
def upload_public_tracking_file(client_token, task_id):
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM clients WHERE tracking_token = %s LIMIT 1", (client_token,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found or tracking link is invalid."}), 404
            
        # Verify task belongs to client
        cursor.execute("SELECT id FROM tasks WHERE id = %s AND client_id = %s LIMIT 1", (task_id, client['id']))
        task = cursor.fetchone()
        if not task:
            return jsonify({"error": "Unauthorized or task not found"}), 403
            
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
            
        # Check size (20MB limit)
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > 20 * 1024 * 1024:
            return jsonify({'error': 'File exceeds maximum limit of 20MB'}), 400
            
        from werkzeug.utils import secure_filename
        from datetime import datetime
        import os
        
        UPLOAD_FOLDER = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'messages')
        )
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        
        return jsonify({'file_url': filename, 'file_name': file.filename, 'file_type': file.content_type}), 201
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error uploading tracking file: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cursor.close(); conn.close()


@client_bp.route('/public/clients/track/<string:client_token>/attachments/<filename>')
def download_public_tracking_file(client_token, filename):
    from app.utils.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM clients WHERE tracking_token = %s LIMIT 1", (client_token,))
        client = cursor.fetchone()
        if not client:
            return jsonify({"error": "Client not found or tracking link is invalid."}), 404
            
        from flask import send_from_directory
        import os
        
        UPLOAD_FOLDER = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'uploads', 'messages')
        )
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error serving tracking file: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cursor.close(); conn.close()

