import os
import sys

# Aggiunge la directory app al PYTHONPATH se necessario
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configura mock environment variables per evitare KeyError durante gli import nei test,
# tranne quando stiamo eseguendo i test live di integrazione
is_live_test = any("test_integration_live" in arg or "test_production_pipeline" in arg for arg in sys.argv)

if not is_live_test:
    os.environ["DATABASE_URL"] = "postgresql://mock_user:mock_password@mock-host:5432/mock-db"
    os.environ["GEMINI_API_KEY"] = "mock-gemini-key"
    os.environ["GOOGLE_API_KEY"] = "mock-google-key"
    os.environ["MINIFLUX_API_URL"] = "http://mock-miniflux"
    os.environ["MINIFLUX_API_KEY"] = "mock-miniflux-key"
    os.environ["OBSIDIAN_VAULT_PATH"] = "/mock/vault"
