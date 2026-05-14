from flask import Blueprint, request, jsonify
from app.models.campaign import Campaign
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

campaigns_bp = Blueprint('campaigns', __name__)

@campaigns_bp.route('/campaigns', methods=['GET'])
@jwt_required()
def get_campaigns():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    campaigns = Campaign.get_all(org_id)
    return jsonify(campaigns), 200

@campaigns_bp.route('/campaigns', methods=['POST'])
@jwt_required()
def create_campaign():
    try:
        claims = get_jwt()
        org_id = claims.get('organisation_id')
        data = request.json
        cid = Campaign.create(
            name=data.get('name'),
            platform=data.get('platform'),
            budget=data.get('budget'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            organisation_id=org_id
        )
        return jsonify({"id": cid, "message": "Campaign created"}), 201
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@campaigns_bp.route('/campaigns/<int:cid>', methods=['PUT'])
@jwt_required()
def update_campaign(cid):
    data = request.json
    Campaign.update(cid, **data)
    return jsonify({"message": "Campaign updated"}), 200

@campaigns_bp.route('/campaigns/<int:cid>', methods=['DELETE'])
@jwt_required()
def delete_campaign(cid):
    Campaign.delete(cid)
    return jsonify({"message": "Campaign deleted"}), 200

@campaigns_bp.route('/campaigns/stats', methods=['GET'])
@jwt_required()
def get_campaign_stats():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    stats = Campaign.get_stats(org_id)
    return jsonify(stats), 200
