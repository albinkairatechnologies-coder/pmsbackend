from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models.task import Task
from app.models.other import Comment, Notification
from app.models.user import User
from app.utils.database import get_db_connection
from datetime import datetime

task_bp = Blueprint('task', __name__)

LEAD_ROLES = ['admin', 'team_lead', 'crm_head', 'marketing_head']

@task_bp.route('/tasks', methods=['POST'])
@jwt_required()
def create_task():
    data = request.json
    claims = get_jwt()
    assigned_by = int(get_jwt_identity())

    # Only admin and team leads can create/assign tasks
    if claims['role'] not in LEAD_ROLES:
        return jsonify({"error": "Only admins and team leads can create tasks"}), 403

    due_date = data.get('due_date') or None
    if due_date:
        try:
            due_dt = datetime.strptime(due_date, '%Y-%m-%d').date()
            if due_dt < datetime.now().date():
                return jsonify({"error": "Due date cannot be in the past"}), 400
        except ValueError:
            return jsonify({"error": "Invalid due date format. Use YYYY-MM-DD"}), 400

    try:
        assigned_to = int(data['assigned_to']) if data.get('assigned_to') else None
        task_id = Task.create(
            title=data['title'],
            description=data.get('description'),
            assigned_by=assigned_by,
            assigned_to=assigned_to,
            team_id=int(data['team_id']) if data.get('team_id') else None,
            department_id=int(data['department_id']) if data.get('department_id') else None,
            client_id=int(data['client_id']) if data.get('client_id') else None,
            department=data.get('department', 'general'),
            status=data.get('status', 'pending'),
            priority=data.get('priority', 'medium'),
            due_date=due_date,
            organisation_id=claims.get('organisation_id')
        )

        # Add participants
        for pid in data.get('participant_ids', []):
            try: Task.add_participant(task_id, int(pid))
            except: pass

        # Add observers
        for oid in data.get('observer_ids', []):
            try: Task.add_observer(task_id, int(oid))
            except: pass

        assigner = User.get_by_id(assigned_by)
        assigner_name = assigner.get('name', 'A Manager') if assigner else "System"

        if assigned_to:
            Notification.create(
                assigned_to,
                "New Task Assigned",
                f"{assigner_name} assigned you: {data['title']}",
                "task",
                f"/dashboard/tasks/{task_id}"
            )
        
        for pid in data.get('participant_ids', []):
            Notification.create(
                int(pid),
                "Added to Task",
                f"{assigner_name} added you as participant to: {data['title']}",
                "task",
                f"/dashboard/tasks/{task_id}"
            )

        for oid in data.get('observer_ids', []):
            Notification.create(
                int(oid),
                "Watching Task",
                f"{assigner_name} listed you as observer on: {data['title']}",
                "task",
                f"/dashboard/tasks/{task_id}"
            )

        return jsonify({"message": "Task created", "task_id": task_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/my-count', methods=['GET'])
@jwt_required()
def get_my_task_count():
    user_id = int(get_jwt_identity())
    claims  = get_jwt()
    org_id  = claims.get('organisation_id')
    conn    = get_db_connection()
    cursor  = conn.cursor()
    try:
        role = claims.get('role', '')
        if role == 'admin':
            org_f = "AND t.organisation_id = %s" if org_id is not None else ""
            params = ([org_id] if org_id is not None else [])
            cursor.execute(f'''
                SELECT COUNT(*) FROM tasks t
                WHERE t.status IN ('pending', 'in_progress') {org_f}
            ''', params)
        elif role in LEAD_ROLES:
            cursor.execute('''
                SELECT COUNT(*) FROM tasks t
                WHERE t.status IN ('pending', 'in_progress')
                AND (t.assignee_id = %s OR t.created_by = %s)
            ''', (user_id, user_id))
        else:
            cursor.execute('''
                SELECT COUNT(*) FROM tasks t
                WHERE t.assignee_id = %s AND t.status IN ('pending', 'in_progress')
            ''', (user_id,))
        count = cursor.fetchone()[0]
    except Exception:
        count = 0
    finally:
        cursor.close(); conn.close()
    return jsonify({'count': count}), 200


@task_bp.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    from datetime import datetime, date
    from decimal import Decimal

    def serialize(row):
        out = {}
        for k, v in row.items():
            if isinstance(v, (datetime, date)):
                out[k] = v.isoformat()
            elif isinstance(v, Decimal):
                out[k] = float(v)
            else:
                out[k] = v
        return out

    user_id = int(get_jwt_identity())
    claims = get_jwt()

    team_id = request.args.get('team_id')
    department_id = request.args.get('department_id')
    status = request.args.get('status')
    client_id = request.args.get('client_id')

    # Auto-run overdue scan
    try:
        check_and_create_overdue_notifications(claims.get('organisation_id'))
    except Exception:
        pass

    if client_id:
        tasks = Task.get_by_client(int(client_id))
    elif claims['role'] == 'admin':
        tasks = Task.get_all(
            team_id=int(team_id) if team_id else None,
            department_id=int(department_id) if department_id else None,
            status=status,
            organisation_id=claims.get('organisation_id')
        )
    elif claims['role'] in LEAD_ROLES:
        tasks = Task.get_for_team_lead(user_id)
    else:
        tasks = Task.get_by_user(user_id)
    return jsonify([serialize(t) for t in tasks]), 200


@task_bp.route('/tasks/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    from datetime import datetime, date
    from decimal import Decimal

    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Serialize datetime/date/Decimal values so jsonify doesn't crash
    serialized = {}
    for k, v in task.items():
        if isinstance(v, (datetime, date)):
            serialized[k] = v.isoformat()
        elif isinstance(v, Decimal):
            serialized[k] = float(v)
        else:
            serialized[k] = v

    serialized['comments']     = Comment.get_by_task(task_id)
    serialized['activity']     = Task.get_activity(task_id)
    serialized['participants'] = Task.get_participants(task_id)
    serialized['observers']    = Task.get_observers(task_id)
    return jsonify(serialized), 200


@task_bp.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    data = request.json
    user_id = int(get_jwt_identity())
    claims = get_jwt()

    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Employees/developers/smm can only update status on assigned or participant tasks
    if claims['role'] not in LEAD_ROLES and claims['role'] != 'admin':
        participants = Task.get_participants(task_id)
        observers    = Task.get_observers(task_id)
        participant_ids = [p['id'] for p in participants]
        observer_ids    = [o['id'] for o in observers]
        if task['assigned_to'] != user_id and user_id not in participant_ids and user_id not in observer_ids:
            return jsonify({"error": "Unauthorized"}), 403
        # Observers can only view — not update
        if user_id in observer_ids and task['assigned_to'] != user_id and user_id not in participant_ids:
            return jsonify({"error": "Observers cannot update tasks"}), 403
        allowed = {'status', 'time_spent'}
        data = {k: v for k, v in data.items() if k in allowed}

    try:
        allowed_fields = {'title', 'description', 'assigned_to', 'team_id', 'department_id',
                          'status', 'priority', 'due_date', 'time_spent', 'department'}
        update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}

        if 'assigned_to' in update_data:
            update_data['assigned_to'] = int(update_data['assigned_to']) if update_data['assigned_to'] else None

        Task.update(task_id, updated_by=user_id, **update_data)
        
        # Notify new assignee if explicitly updated
        if 'assigned_to' in update_data and update_data['assigned_to'] and update_data['assigned_to'] != task.get('assigned_to'):
             u = User.get_by_id(user_id)
             Notification.create(
                 update_data['assigned_to'],
                 "Task Assigned To You",
                 f"{u.get('name', 'A Lead')} re-assigned task: {task['title']}",
                 "task",
                 f"/dashboard/tasks/{task_id}"
             )

        # REWARD LOGIC: AUTOMATIC GOLD COINS on task completion
        if data.get('status') == 'completed' and task.get('assigned_to'):
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Fetch dynamic rules from DB
            cursor.execute("SELECT rule_key, coins FROM coin_rules WHERE is_active = 1")
            rules = {r['rule_key']: r['coins'] for r in cursor.fetchall()}

            base_coins = rules.get('task_completed', 20)
            bonus_coins = rules.get('task_on_time', 30)

            amount = base_coins
            reason = f"Completed task: {task['title']}"

            # Timing bonus
            current_date = datetime.now()
            due_date = None
            if task.get('due_date'):
                try: due_date = datetime.strptime(str(task['due_date']), '%Y-%m-%d %H:%M:%S')
                except:
                    try: due_date = datetime.strptime(str(task['due_date']), '%Y-%m-%d')
                    except: pass

            if due_date and current_date <= due_date:
                amount += bonus_coins
                reason = f"Completed task on time: {task['title']}"

            cursor2 = conn.cursor()
            cursor2.execute("INSERT INTO user_rewards (user_id, amount, reason) VALUES (%s, %s, %s)",
                           (task['assigned_to'], amount, reason))
            conn.commit()
            cursor.close(); cursor2.close(); conn.close()

        return jsonify({"message": "Task updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    claims = get_jwt()
    if claims['role'] != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    conn = __import__('app.utils.database', fromlist=['get_db_connection']).get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    conn.commit()
    cursor.close(); conn.close()
    return jsonify({"message": "Task deleted"}), 200


@task_bp.route('/tasks/<int:task_id>/comments', methods=['POST'])
@jwt_required()
def add_comment(task_id):
    data = request.json
    user_id = int(get_jwt_identity())
    try:
        Comment.create(task_id, user_id, data['comment'])
        # Log activity
        from app.utils.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO task_activity (task_id, user_id, action) VALUES (%s, %s, 'commented')", (task_id, user_id))
        conn.commit()
        cursor.close(); conn.close()
        return jsonify({"message": "Comment added"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/clients/<int:client_id>/stats', methods=['GET'])
@jwt_required()
def get_client_stats(client_id):
    stats = Task.get_stats_by_client(client_id)
    total = sum(s['total'] for s in stats)
    completed = sum(s['completed'] for s in stats)
    percentage = (completed / total * 100) if total > 0 else 0
    return jsonify({
        "total_tasks": total,
        "completed_tasks": completed,
        "percentage": round(percentage, 2),
        "by_department": stats
    }), 200


@task_bp.route('/tasks/<int:task_id>/messages', methods=['GET'])
@jwt_required()
def get_task_messages(task_id):
    messages = Task.get_messages(task_id)
    return jsonify(messages), 200


@task_bp.route('/tasks/<int:task_id>/messages', methods=['POST'])
@jwt_required()
def send_task_message(task_id):
    user_id = int(get_jwt_identity())
    data = request.json
    try:
        msg_id = Task.send_message(
            task_id=task_id,
            user_id=user_id,
            content=data['content'],
            message_type=data.get('message_type', 'text'),
            file_url=data.get('file_url')
        )
        return jsonify({"message": "Message sent", "id": msg_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/<int:task_id>/participants', methods=['POST'])
@jwt_required()
def add_participant(task_id):
    data = request.json
    try:
        target = int(data['user_id'])
        Task.add_participant(task_id, target)
        
        by_u = User.get_by_id(int(get_jwt_identity()))
        t = Task.get_by_id(task_id)
        Notification.create(target, "Invited to Task", f"{by_u.get('name', 'Lead')} invited you to work on: {t['title']}", "task", f"/dashboard/tasks/{task_id}")
        
        return jsonify({"message": "Participant added"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/<int:task_id>/observers', methods=['POST'])
@jwt_required()
def add_observer(task_id):
    data = request.json
    try:
        target = int(data['user_id'])
        Task.add_observer(task_id, target)
        
        by_u = User.get_by_id(int(get_jwt_identity()))
        t = Task.get_by_id(task_id)
        Notification.create(target, "Assigned Observer", f"{by_u.get('name', 'Lead')} made you observer for: {t['title']}", "task", f"/dashboard/tasks/{task_id}")
        
        return jsonify({"message": "Observer added"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/<int:task_id>/participants/<int:user_id>', methods=['DELETE'])
@jwt_required()
def remove_participant(task_id, user_id):
    claims = get_jwt()
    if claims['role'] not in LEAD_ROLES:
        return jsonify({"error": "Unauthorized"}), 403
    try:
        Task.remove_participant(task_id, user_id)
        return jsonify({"message": "Participant removed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/<int:task_id>/observers/<int:user_id>', methods=['DELETE'])
@jwt_required()
def remove_observer(task_id, user_id):
    claims = get_jwt()
    if claims['role'] not in LEAD_ROLES:
        return jsonify({"error": "Unauthorized"}), 403
    try:
        Task.remove_observer(task_id, user_id)
        return jsonify({"message": "Observer removed"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@task_bp.route('/tasks/<int:task_id>/messages/delete/<int:msg_id>', methods=['DELETE'])
@jwt_required()
def delete_task_message(task_id, msg_id):
    user_id = int(get_jwt_identity())
    claims = get_jwt()
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('SELECT user_id FROM task_messages WHERE id = %s', (msg_id,))
        msg = cur.fetchone()
        if not msg:
            cur.close(); conn.close()
            return jsonify({'error': 'Message not found'}), 404
        if claims['role'] != 'admin' and msg['user_id'] != user_id:
            cur.close(); conn.close()
            return jsonify({'error': 'Unauthorized to delete this message'}), 403
        cur.execute('DELETE FROM task_messages WHERE id = %s', (msg_id,))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'message': 'Message deleted'}), 200
    except Exception as e:
        conn.rollback(); cur.close(); conn.close()
        return jsonify({'error': str(e)}), 500


@task_bp.route('/tasks/<int:task_id>/messages/edit/<int:msg_id>', methods=['PUT'])
@jwt_required()
def edit_task_message(task_id, msg_id):
    user_id = int(get_jwt_identity())
    data = request.json
    new_content = data.get('content')
    
    if not new_content or not new_content.strip():
        return jsonify({'error': 'Content cannot be empty'}), 400

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute('SELECT user_id FROM task_messages WHERE id = %s', (msg_id,))
        msg = cur.fetchone()
        if not msg:
            cur.close(); conn.close()
            return jsonify({'error': 'Message not found'}), 404
        if msg['user_id'] != user_id:
            cur.close(); conn.close()
            return jsonify({'error': 'Unauthorized to edit this message'}), 403
        
        cur.execute('UPDATE task_messages SET content = %s, is_edited = 1 WHERE id = %s', (new_content, msg_id))
        conn.commit()
        cur.close(); conn.close()
        return jsonify({'message': 'Message updated'}), 200
    except Exception as e:
        conn.rollback(); cur.close(); conn.close()
        return jsonify({'error': str(e)}), 500


# ── Subtasks API Endpoints ──────────────────────────────────────────

@task_bp.route('/tasks/<int:task_id>/subtasks', methods=['GET'])
@jwt_required()
def get_subtasks(task_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT s.*, u.name as assigned_to_name
            FROM subtasks s
            LEFT JOIN users u ON s.assigned_to = u.id
            WHERE s.task_id = %s
            ORDER BY s.created_at ASC
        """, (task_id,))
        subtasks = cursor.fetchall()
        for s in subtasks:
            if s.get('due_date'):
                s['due_date'] = s['due_date'].isoformat()
            if s.get('created_at'):
                s['created_at'] = s['created_at'].isoformat()
            if s.get('updated_at'):
                s['updated_at'] = s['updated_at'].isoformat()
        return jsonify(subtasks), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@task_bp.route('/tasks/<int:task_id>/subtasks', methods=['POST'])
@jwt_required()
def create_subtask(task_id):
    data = request.json
    title = data.get('title')
    if not title:
        return jsonify({"error": "Title is required"}), 400
    assigned_to = data.get('assigned_to')
    if assigned_to == "" or assigned_to is None:
        assigned_to = None
    else:
        assigned_to = int(assigned_to)

    created_by = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subtasks (task_id, title, assigned_to, created_by)
            VALUES (%s, %s, %s, %s)
        """, (task_id, title, assigned_to, created_by))
        conn.commit()
        subtask_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO task_activity (task_id, user_id, action, new_value)
            VALUES (%s, %s, 'created subtask', %s)
        """, (task_id, created_by, f"Subtask: {title}"))
        conn.commit()

        if assigned_to:
            u = User.get_by_id(created_by)
            Notification.create(
                assigned_to,
                "Subtask Assigned",
                f"{u.get('name', 'A Lead')} assigned subtask '{title}' to you.",
                "task",
                f"/dashboard/tasks/{task_id}"
            )

        return jsonify({"message": "Subtask created", "id": subtask_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@task_bp.route('/tasks/<int:task_id>/subtasks/<int:subtask_id>', methods=['PUT'])
@jwt_required()
def update_subtask(task_id, subtask_id):
    data = request.json
    user_id = int(get_jwt_identity())

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM subtasks WHERE id = %s AND task_id = %s", (subtask_id, task_id))
        old_subtask = cursor.fetchone()
        if not old_subtask:
            return jsonify({"error": "Subtask not found"}), 404

        fields = []
        values = []
        if 'title' in data:
            fields.append("title = %s")
            values.append(data['title'])
        if 'assigned_to' in data:
            assigned_to = data['assigned_to']
            if assigned_to == "" or assigned_to is None:
                assigned_to = None
            else:
                assigned_to = int(assigned_to)
            fields.append("assigned_to = %s")
            values.append(assigned_to)
        if 'is_completed' in data:
            fields.append("is_completed = %s")
            is_completed = 1 if data['is_completed'] else 0
            values.append(is_completed)

        if not fields:
            return jsonify({"message": "No changes to apply"}), 200

        values.append(subtask_id)
        cursor.execute(f"UPDATE subtasks SET {', '.join(fields)} WHERE id = %s", values)

        if 'is_completed' in data and data['is_completed'] != old_subtask['is_completed']:
            action = 'completed subtask' if data['is_completed'] else 'reopened subtask'
            cursor.execute("""
                INSERT INTO task_activity (task_id, user_id, action, new_value)
                VALUES (%s, %s, %s, %s)
            """, (task_id, user_id, action, old_subtask['title']))
        conn.commit()

        return jsonify({"message": "Subtask updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@task_bp.route('/tasks/<int:task_id>/subtasks/<int:subtask_id>', methods=['DELETE'])
@jwt_required()
def delete_subtask(task_id, subtask_id):
    user_id = int(get_jwt_identity())
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT title FROM subtasks WHERE id = %s AND task_id = %s", (subtask_id, task_id))
        sub = cursor.fetchone()
        if not sub:
            return jsonify({"error": "Subtask not found"}), 404

        cursor.execute("DELETE FROM subtasks WHERE id = %s", (subtask_id,))
        cursor.execute("""
            INSERT INTO task_activity (task_id, user_id, action, new_value)
            VALUES (%s, %s, 'deleted subtask', %s)
        """, (task_id, user_id, sub['title']))
        conn.commit()
        return jsonify({"message": "Subtask deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


# ── Project Pipeline API Endpoints ───────────────────────────────────

@task_bp.route('/tasks/<int:task_id>/pipeline', methods=['GET'])
@jwt_required()
def get_task_pipeline(task_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Task not found"}), 404

        cursor.execute("""
            SELECT p.*, u.name as responsible_person_name
            FROM task_pipeline_stages p
            LEFT JOIN users u ON p.responsible_person_id = u.id
            WHERE p.task_id = %s
        """, (task_id,))
        stages = {s['stage_name']: s for s in cursor.fetchall()}

        default_stages = ['planning', 'design', 'development', 'testing', 'client_verification']
        needed_inserts = []
        for name in default_stages:
            if name not in stages:
                needed_inserts.append(name)

        if needed_inserts:
            for name in needed_inserts:
                try:
                    cursor.execute("""
                        INSERT IGNORE INTO task_pipeline_stages (task_id, stage_name, status)
                        VALUES (%s, %s, 'pending')
                    """, (task_id, name))
                except Exception:
                    pass
            conn.commit()

            cursor.execute("""
                SELECT p.*, u.name as responsible_person_name
                FROM task_pipeline_stages p
                LEFT JOIN users u ON p.responsible_person_id = u.id
                WHERE p.task_id = %s
            """, (task_id,))
            stages = {s['stage_name']: s for s in cursor.fetchall()}

        ordered_stages = []
        for name in default_stages:
            s = stages[name]
            if s.get('start_date'):
                s['start_date'] = s['start_date'].isoformat()
            if s.get('end_date'):
                s['end_date'] = s['end_date'].isoformat()
            ordered_stages.append(s)

        return jsonify(ordered_stages), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


@task_bp.route('/tasks/<int:task_id>/pipeline/<string:stage_name>', methods=['PUT'])
@jwt_required()
def update_task_pipeline_stage(task_id, stage_name):
    claims = get_jwt()
    user_id = int(get_jwt_identity())

    if claims['role'] not in LEAD_ROLES and claims['role'] != 'admin':
        return jsonify({"error": "Only admins and team leads can update task pipelines"}), 403

    data = request.json
    start_date = data.get('start_date') or None
    end_date = data.get('end_date') or None
    responsible_person_id = data.get('responsible_person_id')
    if responsible_person_id == "" or responsible_person_id is None:
        responsible_person_id = None
    else:
        responsible_person_id = int(responsible_person_id)

    status = data.get('status', 'pending')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM task_pipeline_stages WHERE task_id = %s AND stage_name = %s", (task_id, stage_name))
        old_stage = cursor.fetchone()
        if not old_stage:
            cursor.execute("""
                INSERT INTO task_pipeline_stages (task_id, stage_name, start_date, end_date, responsible_person_id, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (task_id, stage_name, start_date, end_date, responsible_person_id, status))
            old_status = 'pending'
        else:
            cursor.execute("""
                UPDATE task_pipeline_stages
                SET start_date = %s, end_date = %s, responsible_person_id = %s, status = %s
                WHERE task_id = %s AND stage_name = %s
            """, (start_date, end_date, responsible_person_id, status, task_id, stage_name))
            old_status = old_stage['status']

        if old_status != status:
            cursor.execute("""
                INSERT INTO task_activity (task_id, user_id, action, new_value)
                VALUES (%s, %s, 'updated pipeline stage', %s)
            """, (task_id, user_id, f"Stage: {stage_name} → {status.upper()}"))

        if responsible_person_id and (not old_stage or old_stage['responsible_person_id'] != responsible_person_id):
            u = User.get_by_id(user_id)
            Notification.create(
                responsible_person_id,
                "Assigned Pipeline Phase",
                f"{u.get('name', 'A Lead')} assigned you to lead the '{stage_name.replace('_', ' ').title()}' phase.",
                "task",
                f"/dashboard/tasks/{task_id}"
            )

        conn.commit()
        return jsonify({"message": f"Pipeline stage '{stage_name}' updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close(); conn.close()


# ── Automatic Overdue Task Alert Scanner ─────────────────────────────

def check_and_create_overdue_notifications(org_id=None):
    from app.models.other import Notification
    from app.models.user import User

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT t.id, t.title, t.assigned_to, t.assigned_by, t.due_date,
                   u.name as assignee_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            WHERE t.due_date < CURDATE()
              AND t.status != 'completed'
        """
        params = []
        if org_id is not None:
            query += " AND t.organisation_id = %s"
            params.append(org_id)

        cursor.execute(query, params)
        overdue_tasks = cursor.fetchall()

        for task in overdue_tasks:
            task_id = task['id']
            task_title = task['title']
            assigned_to = task['assigned_to']
            assigned_by = task['assigned_by']
            due_str = task['due_date'].isoformat() if task['due_date'] else 'N/A'
            link = f"/dashboard/tasks/{task_id}"

            if assigned_to:
                cursor.execute("""
                    SELECT COUNT(*) as cnt 
                    FROM notifications 
                    WHERE user_id = %s AND link = %s AND title = 'Task Overdue Alert'
                """, (assigned_to, link))
                if cursor.fetchone()['cnt'] == 0:
                    Notification.create(
                        user_id=assigned_to,
                        title="Task Overdue Alert",
                        message=f"Urgent: Task '{task_title}' was due on {due_str} and is still incomplete!",
                        type="task_overdue",
                        link=link
                    )

            if assigned_by and assigned_by != assigned_to:
                cursor.execute("""
                    SELECT COUNT(*) as cnt 
                    FROM notifications 
                    WHERE user_id = %s AND link = %s AND title = 'Task Overdue Alert (Lead)'
                """, (assigned_by, link))
                if cursor.fetchone()['cnt'] == 0:
                    assignee_lbl = task['assignee_name'] or "Unassigned"
                    Notification.create(
                        user_id=assigned_by,
                        title="Task Overdue Alert (Lead)",
                        message=f"Follow up: Task '{task_title}' (assigned to {assignee_lbl}) is overdue since {due_str}.",
                        type="task_overdue",
                        link=link
                    )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error checking overdue tasks: {e}")
    finally:
        cursor.close(); conn.close()
