import os

class DevConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql://ecopack_user:jXNvyqw4tG7Nu483Nji9KLiqk4ciFs1g@dpg-d6aa2e06fj8s739pui30-a.oregon-postgres.render.com/ecopack_db_az5e"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
