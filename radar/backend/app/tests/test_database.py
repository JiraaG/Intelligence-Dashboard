import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg
from app.core.database import init_pool, bootstrap_database
from app.extraction.state import is_article_duplicate
from app.commit.router import initialize_vault_directories

# ─── Tests for Vault Directory Initialization ───────────────────────────────

def test_initialize_vault_directories(tmp_path) -> None:
    """Verifica che initialize_vault_directories crei le 10 macro-categorie in un path vuoto."""
    vault_dir = tmp_path / "vault"
    
    # Esegue l'inizializzazione sul path temporaneo
    initialize_vault_directories(vault_path=str(vault_dir))
    
    # Categorie attese
    categories = ["Nucleare", "Energia", "Infrastrutture", "Geopolitica", "Economia", "Tecnologia", "Spazio", "Ambiente", "Salute", "Sicurezza"]
    
    # Controlla la presenza fisica delle directory
    assert os.path.exists(vault_dir)
    for cat in categories:
        cat_path = vault_dir / cat
        assert os.path.exists(cat_path)
        assert os.path.isdir(cat_path)


# ─── Tests for Database Core Logic ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_init_pool() -> None:
    """Testa che init_pool crei e restituisca correttamente il pool asyncpg."""
    with patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool:
        mock_pool = MagicMock(spec=asyncpg.Pool)
        mock_create_pool.return_value = mock_pool
        
        pool = await init_pool(db_url="postgresql://mock-host:5432/mock-db")
        
        mock_create_pool.assert_called_once_with(
            "postgresql://mock-host:5432/mock-db",
            min_size=2,
            max_size=10,
            command_timeout=60.0
        )
        assert pool == mock_pool

@pytest.mark.asyncio
async def test_bootstrap_database() -> None:
    """Testa che bootstrap_database esegua le query DDL necessarie all'interno di una transazione."""
    mock_pool = MagicMock(spec=asyncpg.Pool)
    mock_conn = MagicMock(spec=asyncpg.Connection)
    
    # Configura il mock pool in modo che restituisca il mock conn come context manager asincrono
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Configura la transazione come context manager asincrono
    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    
    # Mock dei metodi asincroni
    mock_conn.execute = AsyncMock()
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    
    await bootstrap_database(mock_pool)
    
    # Verifica che sia stata acquisita la connessione e creata la transazione
    mock_pool.acquire.assert_called_once()
    mock_conn.transaction.assert_called_once()
    
    # Asserisce che le tabelle primarie siano state create via execute
    calls = [call[0][0] for call in mock_conn.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS articles" in c for c in calls)
    assert any("CREATE TABLE IF NOT EXISTS companies" in c for c in calls)
    assert any("CREATE TABLE IF NOT EXISTS tags" in c for c in calls)
    assert any("CREATE INDEX IF NOT EXISTS idx_articles_published_at" in c for c in calls)


# ─── Tests for Extraction State Deduplication ────────────────────────────────

@pytest.mark.asyncio
async def test_is_article_duplicate_true() -> None:
    """Testa che is_article_duplicate ritorni True se l'URL esiste già nel DB."""
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_conn.fetchval = AsyncMock(return_value=True)
    
    is_dup = await is_article_duplicate(mock_conn, "https://test.com/dup")
    
    mock_conn.fetchval.assert_called_once_with(
        "SELECT EXISTS(SELECT 1 FROM articles WHERE source_url = $1)",
        "https://test.com/dup"
    )
    assert is_dup is True

@pytest.mark.asyncio
async def test_is_article_duplicate_false() -> None:
    """Testa che is_article_duplicate ritorni False se l'URL non esiste nel DB."""
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_conn.fetchval = AsyncMock(return_value=False)
    
    is_dup = await is_article_duplicate(mock_conn, "https://test.com/new")
    
    assert is_dup is False
