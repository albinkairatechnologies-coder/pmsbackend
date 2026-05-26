"""
Internal WebRTC Signaling via REST polling.
Provides offer/answer/ICE candidate exchange for P2P video calls.
All data stored in-memory — no database required.
Rooms auto-expire after 60 minutes of inactivity.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from threading import Lock
from datetime import datetime, timedelta
import time

videocall_bp = Blueprint('videocall', __name__)

# In-memory store: { room_id: { offer, answer, ice_caller, ice_callee, created_at } }
_rooms: dict = {}
_lock = Lock()

ROOM_TTL_MINUTES = 60


def _cleanup_expired():
    """Remove rooms older than ROOM_TTL_MINUTES."""
    cutoff = datetime.utcnow() - timedelta(minutes=ROOM_TTL_MINUTES)
    to_delete = [rid for rid, r in _rooms.items() if r['created_at'] < cutoff]
    for rid in to_delete:
        del _rooms[rid]


def _get_or_create_room(room_id: str) -> dict:
    if room_id not in _rooms:
        _rooms[room_id] = {
            'offer':      None,
            'answer':     None,
            'ice_caller': [],   # ICE candidates from the caller
            'ice_callee': [],   # ICE candidates from the callee
            'created_at': datetime.utcnow(),
        }
    return _rooms[room_id]


# ── POST offer (caller posts SDP offer) ──────────────────────────────────────
@videocall_bp.route('/rooms/<room_id>/offer', methods=['POST'])
@jwt_required()
def post_offer(room_id: str):
    data = request.get_json(force=True) or {}
    sdp = data.get('sdp')
    if not sdp:
        return jsonify({'error': 'sdp is required'}), 400

    with _lock:
        _cleanup_expired()
        room = _get_or_create_room(room_id)
        # Reset room on new offer (new call started)
        room['offer'] = sdp
        room['answer'] = None
        room['ice_caller'] = []
        room['ice_callee'] = []
        room['created_at'] = datetime.utcnow()

    return jsonify({'status': 'offer stored'}), 201


# ── GET offer (callee polls for SDP offer) ────────────────────────────────────
@videocall_bp.route('/rooms/<room_id>/offer', methods=['GET'])
@jwt_required()
def get_offer(room_id: str):
    with _lock:
        room = _rooms.get(room_id)
        if not room or not room.get('offer'):
            return jsonify({'sdp': None}), 200
    return jsonify({'sdp': room['offer']}), 200


# ── POST answer (callee posts SDP answer) ────────────────────────────────────
@videocall_bp.route('/rooms/<room_id>/answer', methods=['POST'])
@jwt_required()
def post_answer(room_id: str):
    data = request.get_json(force=True) or {}
    sdp = data.get('sdp')
    if not sdp:
        return jsonify({'error': 'sdp is required'}), 400

    with _lock:
        room = _rooms.get(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        room['answer'] = sdp

    return jsonify({'status': 'answer stored'}), 201


# ── GET answer (caller polls for SDP answer) ─────────────────────────────────
@videocall_bp.route('/rooms/<room_id>/answer', methods=['GET'])
@jwt_required()
def get_answer(room_id: str):
    with _lock:
        room = _rooms.get(room_id)
        if not room or not room.get('answer'):
            return jsonify({'sdp': None}), 200
    return jsonify({'sdp': room['answer']}), 200


# ── POST ICE candidate ────────────────────────────────────────────────────────
@videocall_bp.route('/rooms/<room_id>/ice', methods=['POST'])
@jwt_required()
def post_ice(room_id: str):
    data = request.get_json(force=True) or {}
    candidate = data.get('candidate')
    role = data.get('role', 'caller')   # 'caller' or 'callee'

    if not candidate:
        return jsonify({'error': 'candidate is required'}), 400

    with _lock:
        room = _get_or_create_room(room_id)
        key = 'ice_caller' if role == 'caller' else 'ice_callee'
        room[key].append(candidate)

    return jsonify({'status': 'candidate stored'}), 201


# ── GET ICE candidates ────────────────────────────────────────────────────────
@videocall_bp.route('/rooms/<room_id>/ice', methods=['GET'])
@jwt_required()
def get_ice(room_id: str):
    """
    role=caller  → returns callee's ICE candidates
    role=callee  → returns caller's ICE candidates
    since=<int>  → only return candidates from this index onwards
    """
    role = request.args.get('role', 'caller')
    since = int(request.args.get('since', 0))

    with _lock:
        room = _rooms.get(room_id)
        if not room:
            return jsonify({'candidates': [], 'total': 0}), 200
        # Caller wants callee's candidates and vice-versa
        key = 'ice_callee' if role == 'caller' else 'ice_caller'
        candidates = room[key][since:]
        total = len(room[key])

    return jsonify({'candidates': candidates, 'total': total}), 200


# ── DELETE room (hang up / end call) ─────────────────────────────────────────
@videocall_bp.route('/rooms/<room_id>', methods=['DELETE'])
@jwt_required()
def delete_room(room_id: str):
    with _lock:
        _rooms.pop(room_id, None)
    return jsonify({'status': 'room deleted'}), 200


# ── GET room status (check if room exists / has offer) ───────────────────────
@videocall_bp.route('/rooms/<room_id>/status', methods=['GET'])
@jwt_required()
def room_status(room_id: str):
    with _lock:
        room = _rooms.get(room_id)
        if not room:
            return jsonify({'exists': False, 'has_offer': False, 'has_answer': False}), 200
    return jsonify({
        'exists':     True,
        'has_offer':  room['offer'] is not None,
        'has_answer': room['answer'] is not None,
    }), 200
