import os
import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncpg

from app.classification.validator import GeopoliticalArticleSchema
from app.commit.router import slugify_title, get_article_file_path
from app.commit.factory import generate_markdown_content
from app.commit.lock import write_file_with_lock
from app.commit.db_commit import commit_article_to_db, _dedupe_csv_values


def test_dedupe_csv_values_preserves_order() -> None:
    """Tag/company ripetuti dall'LLM devono essere unici prima degli INSERT in-TX."""
    assert _dedupe_csv_values("Economia, Mercati Finanziari, Mercati Finanziari, NOW") == [
        "Economia",
        "Mercati Finanziari",
        "NOW",
    ]
    assert _dedupe_csv_values("Nessuno") == []


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
        title="Impianto Nucleare Zaporizhzhia",
        summary="Monitoraggio reattori.",
        published_at="2026-06-24",
        source_url="https://example.com/zaporizhzhia-nuclear-power-plant",
        country_code="UA",
        latitude=47.5083,
        longitude=34.3981,
        companies_involved="Energoatom",
        tags="Nucleare, Ucraina",
        primary_category="Nucleare",
        sentiment="Neutrale",
        infrastructural_entities="Centrale Zaporizhzhia",
        related_countries="Nessuno",
        relevance_level=4,
    )

    path = get_article_file_path(article, vault_path="/app/vault")

    # Struttura: {vault}/{primary_category}/{country_code}/{published_at}_{slug}_{url_hash}.md
    assert "Nucleare" in path
    assert "UA" in path
    assert path.endswith(".md")
    assert "2026-06-24_impianto-nucleare-zaporizhzhia_" in path


# ─── Tests per la Generazione Markdown (Factory) ─────────────────────────────

def test_generate_markdown_content() -> None:
    """Verifica il rendering delle coordinate Leaflet e l'array piatto dei tag/aziende."""
    article = GeopoliticalArticleSchema(
        title="TAP Pipeline gas Azerbaigian",
        summary="Aumento delle forniture TAP.",
        published_at="2026-06-24",
        source_url="https://example.com/tap-socar",
        country_code="AZ",
        latitude=40.14,
        longitude=47.57,
        companies_involved="TAP AG, SOCAR",
        tags="Energia, Pipeline",
        primary_category="Energia",
        sentiment="Positivo",
        infrastructural_entities="Gasdotto TAP",
        related_countries="CN, US",
        relevance_level=4,
    )

    md = generate_markdown_content(article)

    assert "TAP Pipeline gas Azerbaigian" in md
    assert "location: [40.14, 47.57]" in md
    assert "AZ" in md
    assert "related_countries: [CN, US]" in md
    assert "Energia" in md and "Pipeline" in md
    assert "TAP AG" in md and "SOCAR" in md
    assert "Positivo" in md
    assert "relevance: 4" in md
    assert "https://example.com/tap-socar" in md
    assert "# Riassunto" in md
    assert "Aumento delle forniture TAP." in md
    assert "# Entità Infrastrutturali" in md
    assert "- [[Gasdotto TAP]]" in md
    assert "**Raccordo Relazionale:**" in md
    assert "- Nazione: [[AZ]]" in md
    assert "- Paesi correlati: [[CN]], [[US]]" in md
    assert "- Categoria: [[Energia]]" in md
    assert "[[TAP AG]]" in md and "[[SOCAR]]" in md
    assert "[[Energia]]" in md and "[[Pipeline]]" in md
    # Tag "Energia" collide with category in footer list — still present as wiki link
    assert "- Tag:" in md


# ─── Tests per Scrittura File Concorrente con Lock ───────────────────────────

def test_write_file_with_lock(tmp_path) -> None:
    """Testa che write_file_with_lock crei il file e mantenga il sidecar .lock."""
    target_file = tmp_path / "obsidian" / "test.md"
    content = "Contenuto di test per file lock."

    write_file_with_lock(str(target_file), content)

    assert os.path.exists(target_file)
    with open(target_file, "r", encoding="utf-8") as f:
        assert f.read() == content
    assert os.path.exists(str(target_file) + ".lock")


# ─── Tests per il Commit Relazionale su DB ───────────────────────────────────

@pytest.mark.asyncio
async def test_commit_article_to_db_success() -> None:
    """Verifica l'inserimento relazionale dell'articolo, junction tables e outbox."""
    mock_conn = MagicMock(spec=asyncpg.Connection)

    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    mock_conn.fetchval = AsyncMock()
    mock_conn.fetchval.side_effect = [
        100,  # article ID
        200,  # company_id
        300,  # tag_id
    ]
    mock_conn.execute = AsyncMock()

    article = GeopoliticalArticleSchema(
        title="TSMC Sassonia",
        summary="Apertura fab.",
        published_at="2026-06-24",
        source_url="https://example.com/tsmc",
        country_code="DE",
        latitude=51.0,
        longitude=13.0,
        companies_involved="TSMC",
        tags="Tecnologia",
        primary_category="Tecnologia",
        sentiment="Positivo",
        infrastructural_entities="Nessuno",
        related_countries="FR, US",
        relevance_level=3,
    )

    art_id = await commit_article_to_db(
        mock_conn,
        article,
        outbox_target_path="/app/vault/Tecnologia/DE/2026-06-24_tsmc.md",
        outbox_payload="---\ntitle: TSMC\n---\n",
        miniflux_entry_id=42,
        feed_id=12,
        classification_lane="simple",
        classified_by_model="gemini-2.5-flash",
        dedup_kind="none",
        dedup_action="inserted_new",
    )

    assert art_id == 100
    mock_conn.transaction.assert_called_once()

    insert_call_args = mock_conn.fetchval.call_args_list[0][0]
    assert "sentiment" in insert_call_args[0]
    assert "relevance_level" in insert_call_args[0]
    assert insert_call_args[9] == "Positivo"
    assert insert_call_args[10] == 3
    assert insert_call_args[13] == ["FR", "US"]
    assert insert_call_args[15] == 12  # feed_id ($15)
    assert insert_call_args[17] == "simple"  # classification_lane ($17)
    assert insert_call_args[21] == "none"  # dedup_kind ($21)
    assert insert_call_args[23] == "inserted_new"  # dedup_action ($23)

    exec_calls = [call[0][0] for call in mock_conn.execute.call_args_list]
    assert any("INSERT INTO article_companies" in c for c in exec_calls)
    assert any("INSERT INTO article_tags" in c for c in exec_calls)
    assert any("INSERT INTO article_outbox" in c for c in exec_calls)


@pytest.mark.asyncio
async def test_commit_article_to_db_conflict_fallback() -> None:
    """Verifica che in caso di conflitto dell'URL, recuperi l'ID esistente e proceda."""
    mock_conn = MagicMock(spec=asyncpg.Connection)

    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    mock_conn.fetchval = AsyncMock()
    mock_conn.fetchval.side_effect = [None, 105, 201, 301]
    mock_conn.execute = AsyncMock()

    article = GeopoliticalArticleSchema(
        title="TSMC Sassonia",
        summary="Apertura fab.",
        published_at="2026-06-24",
        source_url="https://Example.com/tsmc/",
        country_code="DE",
        latitude=51.0,
        longitude=13.0,
        companies_involved="TSMC",
        tags="Tecnologia",
        primary_category="Tecnologia",
        sentiment="Positivo",
        infrastructural_entities="Nessuno",
        related_countries="Nessuno",
        relevance_level=3,
    )

    art_id = await commit_article_to_db(
        mock_conn,
        article,
        outbox_target_path="/app/vault/Tecnologia/DE/article.md",
        outbox_payload="payload",
        miniflux_entry_id=7,
    )

    assert art_id == 105
    select_call_args = mock_conn.fetchval.call_args_list[1][0]
    assert "SELECT id FROM articles WHERE source_url = $1" in select_call_args[0]
    assert select_call_args[1] == "https://example.com/tsmc"


@pytest.mark.asyncio
async def test_commit_article_dedupes_repeated_tags() -> None:
    """Tag CSV ripetuti non devono generare due INSERT sullo stesso name in-TX."""
    mock_conn = MagicMock(spec=asyncpg.Connection)
    mock_transaction = MagicMock()
    mock_conn.transaction.return_value = mock_transaction
    mock_transaction.__aenter__ = AsyncMock()
    mock_transaction.__aexit__ = AsyncMock()

    # article → company ServiceNow → tag Economia → SELECT skip → tag Mercati → SELECT skip
    # Pattern: INSERT DO NOTHING RETURNING None when already exists → SELECT id
    async def _fetchval(query, *args):
        q = query if isinstance(query, str) else ""
        if "INSERT INTO articles" in q:
            return 501
        if "INSERT INTO companies" in q:
            return 601
        if "INSERT INTO tags" in q:
            return None  # already exists → fallback SELECT
        if "SELECT id FROM tags" in q:
            return 701 if args and args[0] == "Economia" else 702
        if "SELECT id FROM companies" in q:
            return 601
        return None

    mock_conn.fetchval = AsyncMock(side_effect=_fetchval)
    mock_conn.execute = AsyncMock()

    article = GeopoliticalArticleSchema(
        title="Should You Buy ServiceNow (NOW) Before Earnings?",
        summary="Analisi pre-earnings.",
        published_at="2026-07-22",
        source_url="https://example.com/now-earnings",
        country_code="US",
        latitude=40.7,
        longitude=-74.0,
        companies_involved="ServiceNow, ServiceNow",
        tags="Economia, Mercati Finanziari, Mercati Finanziari",
        primary_category="Economia",
        sentiment="Neutrale",
        infrastructural_entities="Nessuno",
        related_countries="Nessuno",
        relevance_level=3,
    )

    art_id = await commit_article_to_db(
        mock_conn,
        article,
        feed_title="Yahoo Finance",
        outbox_target_path="/app/vault/Economia/US/now.md",
        outbox_payload="payload",
        miniflux_entry_id=99,
    )

    assert art_id == 501
    tag_inserts = [
        c
        for c in mock_conn.fetchval.call_args_list
        if isinstance(c[0][0], str) and "INSERT INTO tags" in c[0][0]
    ]
    assert len(tag_inserts) == 2  # Economia + Mercati Finanziari (una sola volta)
    assert {c[0][1] for c in tag_inserts} == {"Economia", "Mercati Finanziari"}
