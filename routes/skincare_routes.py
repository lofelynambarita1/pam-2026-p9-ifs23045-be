import logging
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions import db, limiter
from models.skincare_routine import SkincareRoutine
from services.ai_service import generate_skincare_routine

logger = logging.getLogger(__name__)

skincare_bp = Blueprint("skincare", __name__)

VALID_SKIN_TYPES = {"oily", "dry", "combination", "normal", "sensitive"}
VALID_BUDGETS = {"low", "medium", "high"}


@skincare_bp.route("", methods=["GET"])
@jwt_required()
def get_routines():
    user_id = int(get_jwt_identity())

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    per_page = min(per_page, 50)

    pagination = SkincareRoutine.query.filter_by(user_id=user_id)\
        .order_by(SkincareRoutine.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "data": [r.to_dict() for r in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages
    }), 200


@skincare_bp.route("/<int:routine_id>", methods=["GET"])
@jwt_required()
def get_routine(routine_id):
    user_id = int(get_jwt_identity())
    routine = SkincareRoutine.query.filter_by(id=routine_id, user_id=user_id).first()

    if not routine:
        return jsonify({"message": "Rutinitas tidak ditemukan"}), 404

    return jsonify({"data": routine.to_dict()}), 200


@skincare_bp.route("/generate", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute;50 per day")
def generate():
    user_id = int(get_jwt_identity())
    data = request.get_json()

    if not data:
        return jsonify({"message": "Request body diperlukan"}), 400

    skin_type = data.get("skin_type", "").strip().lower()
    skin_concerns = data.get("skin_concerns", "").strip()
    budget = data.get("budget", "").strip().lower()

    if not skin_type:
        return jsonify({"message": "skin_type wajib diisi"}), 400
    if skin_type not in VALID_SKIN_TYPES:
        return jsonify({"message": f"skin_type harus salah satu dari: {', '.join(VALID_SKIN_TYPES)}"}), 400
    if not skin_concerns:
        return jsonify({"message": "skin_concerns wajib diisi"}), 400
    if not budget:
        return jsonify({"message": "budget wajib diisi"}), 400
    if budget not in VALID_BUDGETS:
        return jsonify({"message": f"budget harus salah satu dari: {', '.join(VALID_BUDGETS)}"}), 400

    try:
        result = generate_skincare_routine(skin_type, skin_concerns, budget)
    except Exception as e:
        logger.error("AI generation failed for user %s: %s", user_id, str(e))
        return jsonify({"message": "Gagal generate rutinitas. Silakan coba lagi."}), 500

    routine = SkincareRoutine(
        user_id=user_id,
        skin_type=skin_type,
        skin_concerns=skin_concerns,
        budget=budget,
        routine_title=result.get("routine_title", "Personalized Skincare Routine"),
        morning_routine=json.dumps(result.get("morning_routine", []), ensure_ascii=False),
        evening_routine=json.dumps(result.get("evening_routine", []), ensure_ascii=False),
        product_recommendations=json.dumps(result.get("product_recommendations", []), ensure_ascii=False),
        tips=json.dumps(result.get("tips", []), ensure_ascii=False),
        summary=result.get("summary", "")
    )

    db.session.add(routine)
    db.session.commit()

    return jsonify({"data": routine.to_dict()}), 200


@skincare_bp.route("/<int:routine_id>", methods=["DELETE"])
@jwt_required()
def delete_routine(routine_id):
    user_id = int(get_jwt_identity())
    routine = SkincareRoutine.query.filter_by(id=routine_id, user_id=user_id).first()

    if not routine:
        return jsonify({"message": "Rutinitas tidak ditemukan"}), 404

    db.session.delete(routine)
    db.session.commit()

    return jsonify({"message": "Rutinitas berhasil dihapus"}), 200
