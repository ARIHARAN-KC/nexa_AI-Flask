import os
from urllib.parse import urlparse


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    UPLOAD_FOLDER = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        "static/uploads"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300
    }

    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        parsed = urlparse(database_url)

        SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{parsed.username}:{parsed.password}"
            f"@{parsed.hostname}:{parsed.port or 5432}"
            f"{parsed.path}?sslmode=require"
        )
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///nexa_workspace.db"
