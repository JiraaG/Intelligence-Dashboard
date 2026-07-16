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
async def test_init_pool_retries_cannot_connect_now() -> None:
    """Compose restart race: retry CannotConnectNowError then succeed."""
    mock_pool = MagicMock(spec=asyncpg.Pool)
    with (
        patch("asyncpg.create_pool", new_callable=AsyncMock) as mock_create_pool,
        patch("app.core.database.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_create_pool.side_effect = [
            asyncpg.CannotConnectNowError("the database system is starting up"),
            mock_pool,
        ]
        pool = await init_pool(db_url="postgresql://mock-host:5432/mock-db")
        assert pool == mock_pool
        assert mock_create_pool.await_count == 2
        mock_sleep.assert_awaited()

@pytest.mark.asyncio
async def test_bootstrap_database() -> None:
    """Testa che bootstrap_database deleghi a run_migrations."""
    mock_pool = MagicMock(spec=asyncpg.Pool)

    with patch("app.core.database.run_migrations", new_callable=AsyncMock) as mock_run:
        await bootstrap_database(mock_pool)
        mock_run.assert_awaited_once_with(mock_pool)


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
