from extensions import db
from datetime import datetime


class SkincareRoutine(db.Model):
    __tablename__ = "skincare_routines"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Input dari user
    skin_type = db.Column(db.String(50), nullable=False)        # oily, dry, combination, normal, sensitive
    skin_concerns = db.Column(db.Text, nullable=False)           # acne, dark spots, wrinkles, dll
    budget = db.Column(db.String(50), nullable=False)            # low, medium, high

    # Output dari AI
    routine_title = db.Column(db.String(256), nullable=False)
    morning_routine = db.Column(db.Text, nullable=False)         # JSON string: list of steps
    evening_routine = db.Column(db.Text, nullable=False)         # JSON string: list of steps
    product_recommendations = db.Column(db.Text, nullable=True)  # JSON string: list of products
    tips = db.Column(db.Text, nullable=True)                     # JSON string: list of tips
    summary = db.Column(db.Text, nullable=True)                  # General summary/advice

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json

        def safe_json_list(text):
            if not text:
                return []
            try:
                result = json.loads(text)
                return result if isinstance(result, list) else []
            except (json.JSONDecodeError, ValueError):
                return []

        return {
            "id": self.id,
            "user_id": self.user_id,
            "skin_type": self.skin_type,
            "skin_concerns": self.skin_concerns,
            "budget": self.budget,
            "routine_title": self.routine_title,
            "morning_routine": safe_json_list(self.morning_routine),
            "evening_routine": safe_json_list(self.evening_routine),
            "product_recommendations": safe_json_list(self.product_recommendations),
            "tips": safe_json_list(self.tips),
            "summary": self.summary or "",
            "created_at": self.created_at.isoformat()
        }
