import os
from dotenv import load_dotenv

# Carica il file .env all'importazione del modulo
load_dotenv()

# Priorità GOOGLE_API_KEY, fallback automatico su GEMINI_API_KEY
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

LLM_API_KEY = GOOGLE_API_KEY or GEMINI_API_KEY
if not LLM_API_KEY:
    raise ValueError("Configurazione Errata: Manca GOOGLE_API_KEY o GEMINI_API_KEY nel file .env")

# Configurazione del modello con default "gemma-4-31b-it"
_raw_model = os.getenv("GEMINI_MODEL", "gemma-4-31b")
GEMINI_MODEL = "gemma-4-31b-it" if _raw_model in ("gemma-4-31b", "gemma-4-31b-it") else _raw_model

# Altre configurazioni globali con relativi default o fallback
pg_user = os.getenv("POSTGRES_USER", "radar_user")
pg_pass = os.getenv("POSTGRES_PASSWORD", "radar_password_secure")
pg_db = os.getenv("POSTGRES_DB", "radar_db")
pg_host = os.getenv("POSTGRES_HOST", "localhost")
pg_port = os.getenv("POSTGRES_PORT", "5432")
default_db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"

DATABASE_URL = os.getenv("DATABASE_URL", default_db_url)
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/app/vault")

# Configurazione Miniflux
MINIFLUX_API_URL = os.getenv("MINIFLUX_API_URL", "http://localhost:8080")
MINIFLUX_API_KEY = os.getenv("MINIFLUX_API_KEY", "")
MINIFLUX_LIMIT = int(os.getenv("MINIFLUX_LIMIT", "50"))
