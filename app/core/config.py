import os
from pathlib import Path

# Best practice: Load secrets from environment variables
# For simplicity in this phase, we use a default secret key.
SECRET_KEY = os.environ.get("SECRET_KEY", "a-default-secret-key-for-development")

# Database configuration
BASE_DIR = Path(__file__).resolve().parent.parent
SQLALCHEMY_DATABASE_URI = (
    os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'instance' / 'agent.db'}"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Scheduler configuration
SCHEDULER_API_ENABLED = True
