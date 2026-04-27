from dotenv import load_dotenv
load_dotenv()

import os
import logging
from flask import Flask
from flask_cors import CORS
from config import Config
from extensions import db, jwt, limiter

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    for warning in Config.validate():
        logger.warning("[CONFIG] %s", warning)

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    allowed_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    CORS(app, origins=allowed_origins if allowed_origins else "*")

    from routes.auth_routes import auth_bp
    from routes.skincare_routes import skincare_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(skincare_bp, url_prefix="/skincare")

    @app.route("/")
    def health_check():
        from datetime import datetime
        return {
            "status": "ok",
            "message": "SkincareAI backend is running 🌸",
            "timestamp": datetime.utcnow().isoformat()
        }, 200

    with app.app_context():
        db.create_all()

        from models.user import User
        from werkzeug.security import generate_password_hash

        if not User.query.filter_by(username="admin").first():
            admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
            admin = User(
                username="admin",
                password=generate_password_hash(admin_password),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("[SEED] Admin account created.")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    port = int(os.environ.get("PORT", 31151))
    app.run(debug=False, port=port)
