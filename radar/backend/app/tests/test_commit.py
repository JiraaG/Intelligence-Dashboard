import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg

from app.classification.validator import GeopoliticalArticleSchema
from app.commit.router import slugify_title, get_article_file_path
from app.commit.factory import generate_markdown_content
from app.commit.lock import write_file_with_lock
from app.commit.db_commit import commit_article_to_db

# ─── Tests per la Slugificazione ed il Routing del Vault ─────────────────────

def test_slugify_title_basic() -> None:
    """Verifica la corretta pulizia di titoli ordinari."""
    assert slugify_title("TSMC in Sassonia") == "tsmc-in-sassonia"

def test_slugify_title_ntfs_chars() -> None:
    """Verifica che i caratteri vietati NTFS/FAT vengano correttamente rimossi e sostituiti."""
    illegal_title = 'Chip: Intel & AMD / "Scontro del Secolo"?'
    clean = slugify_title(illegal_title)
    # : / " ? dovrebbero essere sostituiti con trattini, e i trattini multipli collassati
    assert ":" not in clean
    assert "/" not in clean
    assert '"' not in clean
    assert "?" not in clean
    assert "--" not in clean
    assert clean == "chip-intel-&-amd-scontro-del-secolo"

def test_get_article_file_path() -> None:
    """Verifica la compilazione del percorso e del nome file comprensivo di URL hash."""
    article = GeopoliticalArticleSchema(
        reasoning="Test reasoning.",
        title="Impianto Nucleare Zaporizhzhia",
        summary="Monitoraggio reattori.",
        published_at="2026-06-24",
        source_url="https://example.com/zaporizhzhia-nuclear-power-plant",
        country_code="UA",
        latitude=47.5083,
        longitude=34.3981,
        companies_involved=["Energoatom"],
        tags=["Nucleare", "Ucraina"],
        primary_category="Nucleare",
        sentiment="Neutrale",
        infrastructural_entities=["Centrale Zaporizhzhia"],
        relevance_level=4
    )
    
    path = get_article_file_path(article, vault_path="/app/vault")
    
    # Struttura attesa: /app/vault/{primary_category}/{country_code}/{published_at}_{slugified_title}_{url_hash}.md
    assert path.startswith(os.path.join("/app/vault", "Nucleare", "UA"))
    assert path.endswith(".md")
    assert "2026-06-24_impianto-nucleare-zaporizhzhia_" in path


# ─── Tests per la Generazione Markdown (Factory) ─────────────────────────────

def test_generate_markdown_content() -> None:
    """Verifica il rendering delle coordinate Leaflet e l'array piatto dei tag/aziende."""
    article = GeopoliticalArticleSchema(
        reasoning="CoT reasoning.",
        title="TAP Pipeline gas Azerbaigian",
        summary="Aumento delle forniture TAP.",
        published_at="2026-06-24",
        source_url="https://example.com/tap-socar",
        country_code="AZ",
        latitude=40.14,
        longitude=47.57,
        companies_involved=["TAP AG", "SOCAR"],
        tags=["Energia", "Pipeline"],
        primary_category="Energia",
        sentiment="Positivo",
        infrastructural_entities=["Gasdotto TAP"],
        relevance_level=4
    )
    
    md = generate_markdown_content(article)
    
    # Controlla la presenza del Frontmatter e le specifiche Leaflet / YAML piatti
    assert 'title: "TAP Pipeline gas Azerbaigian"' in md
    assert "location: [40.14, 47.57]" in md
    assert 'country: "AZ"' in md
    assert 'tags: ["Energia", "Pipeline"]' in md
    assert 'companies: ["TAP AG", "SOCAR"]' in md
    assert 'sentiment: "Positivo"' in md
    assert "relevance: 4" in md
    assert "source: \"https://example.com/tap-socar\"" in md
    
    # Controlla il corpo del Markdown
    assert "# Riassunto" in md
    assert "Aumento delle forniture TAP." in md
    assert "# Entità Infrastrutturali" in md
    assert "- Gasdotto TAP" in md


# ─── Tests per Scrittura File Concorrente con Lock ───────────────────────────

def test_write_file_with_lock(tmp_path) -> None:
    """Testa che write_file_with_lock crei correttamente il file e rimuova i lock temporanei."""
    target_file = tmp_path / "obsidian" / "test.md"
    content = "Contenuto di test per file lock."
    
    # Scrive il file con il lock
    write_file_with_lock(str(target_file), content)
    
    # Asserisce la creazione fisica e l'assenza di residui del file .lock
    assert os.path.exists(target_file)
    with open(target_file, "r", encoding="utf-8") as f:
        assert f.read() == content
    assert not os.path.exists(str(target_file) + ".lock")


# ─── Tests per il Commit Relazionale su DB ───────────────────────────────────

@pytest.mark.asyncio
async def test_commit_article_to_db_success() -> None:
    """Verifica l'inserimento relazionale dell'articolo e l'upsert nelle tabelle connesse."""
    mock_conn = MagicMock(spec=asyncpg.Connection)
    
    # Mock della transazione
    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    
    # Configura il mock conn.fetchval per restituire l'ID dell'articolo inserito
    mock_conn.fetchval = AsyncMock()
    mock_conn.fetchval.side_effect = [
        100,  # Primo colpo: fetchval per l'articolo ID (100)
        200,  # Secondo colpo: select company_id (200)
        300   # Terzo colpo: select tag_id (300)
    ]
    mock_conn.execute = AsyncMock()
    
    article = GeopoliticalArticleSchema(
        reasoning="Ragionamento.",
        title="TSMC Sassonia",
        summary="Apertura fab.",
        published_at="2026-06-24",
        source_url="https://example.com/tsmc",
        country_code="DE",
        latitude=51.0,
        longitude=13.0,
        companies_involved=["TSMC"],
        tags=["Chip"],
        primary_category="Chip",
        sentiment="Positivo",
        infrastructural_entities=[],
        relevance_level=3
    )
    
    art_id = await commit_article_to_db(mock_conn, article)
    
    assert art_id == 100
    mock_conn.transaction.assert_called_once()
    
    # Assicura che sentiment e relevance_level vengano inseriti nel DB
    insert_call_args = mock_conn.fetchval.call_args_list[0][0]
    assert "sentiment" in insert_call_args[0]
    assert "relevance_level" in insert_call_args[0]
    
    # Controlla i valori estratti passati
    assert insert_call_args[9] == "Positivo"  # sentiment
    assert insert_call_args[10] == 3           # relevance_level
    
    # Controlla che le query di associazione junction table siano state eseguite
    exec_calls = [call[0][0] for call in mock_conn.execute.call_args_list]
    assert any("INSERT INTO article_companies" in c for c in exec_calls)
    assert any("INSERT INTO article_tags" in c for c in exec_calls)

@pytest.mark.asyncio
async def test_commit_article_to_db_conflict_fallback() -> None:
    """Verifica che in caso di conflitto dell'URL, recuperi l'ID esistente e proceda."""
    mock_conn = MagicMock(spec=asyncpg.Connection)
    
    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()
    
    # Primo colpo: fetchval per l'articolo restituisce None (conflitto UNIQUE)
    # Secondo colpo: SELECT ID dell'articolo esistente restituisce 105
    # Terzo colpo: select company_id (201)
    mock_conn.fetchval = AsyncMock()
    mock_conn.fetchval.side_effect = [None, 105, 201]
    mock_conn.execute = AsyncMock()
    
    article = GeopoliticalArticleSchema(
        reasoning="Ragionamento.",
        title="TSMC Sassonia",
        summary="Apertura fab.",
        published_at="2026-06-24",
        source_url="https://example.com/tsmc",
        country_code="DE",
        latitude=51.0,
        longitude=13.0,
        companies_involved=["TSMC"],
        tags=[],
        primary_category="Chip",
        sentiment="Positivo",
        infrastructural_entities=[],
        relevance_level=3
    )
    
    art_id = await commit_article_to_db(mock_conn, article)
    
    assert art_id == 105
    # Verifica che sia stato eseguito il recupero tramite SELECT URL
    select_call_args = mock_conn.fetchval.call_args_list[1][0]
    assert "SELECT id FROM articles WHERE source_url = $1" in select_call_args[0]
    assert select_call_args[1] == "https://example.com/tsmc"
