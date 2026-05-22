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

