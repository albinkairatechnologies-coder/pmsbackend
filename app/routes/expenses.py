from flask import Blueprint, request, jsonify
from app.models.expense import Expense
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/expenses', methods=['GET'])
@jwt_required()
def get_expenses():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    expenses = Expense.get_all(org_id, category, start_date, end_date)
    return jsonify(expenses), 200

@expenses_bp.route('/expenses', methods=['POST'])
@jwt_required()
def create_expense():
    try:
        claims = get_jwt()
        org_id = claims.get('organisation_id')
        user_id = int(get_jwt_identity())
        data = request.json
        eid = Expense.create(
            title=data.get('title'),
            category=data.get('category'),
            amount=data.get('amount'),
            expense_date=data.get('expense_date'),
            description=data.get('description'),
            organisation_id=org_id,
            added_by=user_id
        )
        return jsonify({"id": eid, "message": "Expense created"}), 201
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@expenses_bp.route('/expenses/stats', methods=['GET'])
@jwt_required()
def get_expense_stats():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    stats = Expense.get_stats(org_id)
    return jsonify(stats), 200

@expenses_bp.route('/expenses/monthly-summary', methods=['GET'])
@jwt_required()
def get_monthly_summary():
    claims = get_jwt()
    org_id = claims.get('organisation_id')
    summary = Expense.get_monthly_summary(org_id)
    return jsonify(summary), 200

@expenses_bp.route('/expenses/<int:eid>', methods=['DELETE'])
@jwt_required()
def delete_expense(eid):
    Expense.delete(eid)
    return jsonify({"message": "Expense deleted"}), 200
