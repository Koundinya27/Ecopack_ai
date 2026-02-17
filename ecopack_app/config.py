import os

class DevConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:ssskoundi123@localhost:5432/ecopack_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
