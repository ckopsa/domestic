import os
from dotenv import load_dotenv

load_dotenv()

# Database configuration
DB_USER = os.getenv("DB_USER", "user")
DB_PASS = os.getenv("DB_PASS", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "checklist_db")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Keycloak configuration
KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "domestic_workflow")
KEYCLOAK_API_CLIENT_ID = os.getenv("KEYCLOAK_API_CLIENT_ID", "backend-api")
KEYCLOAK_API_CLIENT_SECRET = os.getenv("KEYCLOAK_API_CLIENT_SECRET", "UTxvTHtNaNPKct1vXkad8zAXZNsyzg5f")
