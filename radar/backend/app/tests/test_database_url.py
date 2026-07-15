import importlib
import app.core.config


def test_database_url_encoding(monkeypatch) -> None:
    # Ensure DATABASE_URL is not set so we use the default_db_url construction
    monkeypatch.delenv("DATABASE_URL", raising=False)

    # Set credentials containing special characters
    monkeypatch.setenv("POSTGRES_USER", "user@name")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:w/rd#1")
    monkeypatch.setenv("POSTGRES_DB", "db_name")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")

    # Force reload of app.core.config to apply mock env vars
    importlib.reload(app.core.config)

    db_url = app.core.config.DATABASE_URL

    # Expected encoded user: "user%40name"
    # Expected encoded password: "p%40ss%3Aw%2Frd%231"
    assert "user%40name" in db_url
    assert "p%40ss%3Aw%2Frd%231" in db_url
    assert "@localhost:5432/db_name" in db_url

    # Cleanup: restore env and reload config again
    monkeypatch.undo()
    importlib.reload(app.core.config)
