from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from ecopack_app.config import DevConfig
db = SQLAlchemy()

def create_app():
    app = Flask(__name__,instance_relative_config=True)

    from .config import DevConfig
    app.config.from_object(DevConfig)

    db.init_app(app)

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    from .api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")


    with app.app_context():
        from . import models
        db.create_all()

    return app
