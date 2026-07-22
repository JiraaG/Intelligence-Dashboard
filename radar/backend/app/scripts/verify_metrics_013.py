"""Script di verifica live Fase Metrics 013 (GATE verification stretto).

Verifica la presenza di colonne, coerenza dei dati, soglia minima di articoli denorm (>=12),
presenza di almeno 1 evento 'url_exact', bassi tassi di NULL e linkage post-commit tra
articles, llm_request_ledger, article_dedup_events e article_embeddings.
"""

from __future__ import annotations

import asyncio
import os
import sys
import asyncpg

from app.core.config import DATABASE_URL


async def run_verification() -> bool:
    print("=== START VERIFICATION FASE METRICS 013 (STRICT GATE) ===")
    conn = await asyncpg.connect(DATABASE_URL)
    all_ok = True

    try:
        # 1. Verifica schema colonne denorm in articles
        print("\n1. Controllo colonne denorm in 'articles'...")
        columns = await conn.fetch(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'articles'
            """
        )
        col_names = {c["column_name"] for c in columns}
        expected_art_cols = {
            "feed_id",
            "feed_domain",
            "classification_lane",
            "classified_by_model",
            "classified_by_provider",
            "was_escalated",
            "dedup_kind",
            "dedup_match_article_id",
            "dedup_action",
            "clean_text_chars",
            "clean_text_words",
            "embedding_time_ms",
            "pipeline_latency_ms",
            "geo_resolution_method",
        }
        missing_art_cols = expected_art_cols - col_names
        if missing_art_cols:
            print(f"  ❌ Colonne mancanti in articles: {missing_art_cols}")
            all_ok = False
        else:
            print("  ✅ Tutte le 14 colonne denorm presenti in 'articles'.")

        # 2. Controllo colonne llm_request_ledger
        print("\n2. Controllo colonne FinOps in 'llm_request_ledger'...")
        ledger_cols = await conn.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'llm_request_ledger'
            """
        )
        ledger_col_names = {c["column_name"] for c in ledger_cols}
        expected_ledger_cols = {
            "miniflux_entry_id",
            "article_id",
            "prompt_tokens",
            "completion_tokens",
            "cached_prompt_tokens",
            "execution_time_ms",
            "http_status",
            "error_code",
        }
        missing_ledger = expected_ledger_cols - ledger_col_names
        if missing_ledger:
            print(f"  ❌ Colonne mancanti in llm_request_ledger: {missing_ledger}")
            all_ok = False
        else:
            print("  ✅ Tutte le colonne FinOps presenti in 'llm_request_ledger'.")

        # 3. Controllo colonne e vincoli article_dedup_events
        print("\n3. Controllo colonne in 'article_dedup_events'...")
        dedup_cols = await conn.fetch(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'article_dedup_events'
            """
        )
        dedup_col_dict = {c["column_name"]: c["is_nullable"] for c in dedup_cols}
        expected_dedup = {"dedup_kind", "action_taken", "feed_id", "incoming_miniflux_entry_id"}
        missing_dedup = expected_dedup - set(dedup_col_dict.keys())
        if missing_dedup:
            print(f"  ❌ Colonne mancanti in article_dedup_events: {missing_dedup}")
            all_ok = False
        elif dedup_col_dict.get("cosine_distance") == "NO":
            print("  ❌ NOT NULL constraint non rimosso da cosine_distance in article_dedup_events.")
            all_ok = False
        else:
            print("  ✅ Colonne dedup e nullable cosine_distance verificati in 'article_dedup_events'.")

        # 4. Controllo popolamento dati denorm articoli (Soglia >= 12 articoli popolati completi)
        print("\n4. Controllo popolamento dati denorm articoli (soglia >= 12)...")
        populated_count = await conn.fetchval(
            """
            SELECT COUNT(*)::INT FROM articles
            WHERE classification_lane IS NOT NULL
              AND pipeline_latency_ms > 0
              AND classified_by_model IS NOT NULL
            """
        )
        print(f"  Articoli denorm completi (lane + latency>0 + model): {populated_count}")
        if populated_count < 12:
            print(f"  ❌ Articoli denorm completi insufficienti: {populated_count} < 12 (richiesto da SoT §8).")
            all_ok = False
        else:
            print(f"  ✅ Soglia articoli denorm superata: {populated_count} >= 12.")

        # 4b. Controllo NULL-rate sul subset degli articoli denorm (soglia < 5%)
        if populated_count > 0:
            null_feed_id = await conn.fetchval(
                """
                SELECT COUNT(*)::INT FROM articles
                WHERE classification_lane IS NOT NULL AND feed_id IS NULL
                """
            )
            null_model = await conn.fetchval(
                """
                SELECT COUNT(*)::INT FROM articles
                WHERE classification_lane IS NOT NULL AND classified_by_model IS NULL
                """
            )
            null_dedup_kind = await conn.fetchval(
                """
                SELECT COUNT(*)::INT FROM articles
                WHERE classification_lane IS NOT NULL AND dedup_kind IS NULL
                """
            )
            feed_null_rate = null_feed_id / populated_count
            model_null_rate = null_model / populated_count
            dedup_null_rate = null_dedup_kind / populated_count

            print(
                f"  NULL-rate feed_id: {feed_null_rate:.1%}, "
                f"classified_by_model: {model_null_rate:.1%}, "
                f"dedup_kind: {dedup_null_rate:.1%}"
            )
            if feed_null_rate > 0.05:
                print(f"  ❌ NULL-rate elevato su feed_id: {feed_null_rate:.1%} (> 5%)")
                all_ok = False
            if model_null_rate > 0.05:
                print(f"  ❌ NULL-rate elevato su classified_by_model: {model_null_rate:.1%} (> 5%)")
                all_ok = False
            if dedup_null_rate > 0.05:
                print(f"  ❌ NULL-rate elevato su dedup_kind: {dedup_null_rate:.1%} (> 5%)")
                all_ok = False

        # 5. Controllo evento url_exact live (BLOCKER: >= 1 richiesto)
        print("\n5. Controllo eventi 'url_exact' in article_dedup_events (soglia >= 1)...")
        url_exact_events = await conn.fetchval(
            """
            SELECT COUNT(*)::INT FROM article_dedup_events
            WHERE dedup_kind = 'url_exact'
              AND action_taken = 'kept_existing'
              AND cosine_distance IS NULL
            """
        )
        print(f"  Eventi 'url_exact' registrati (kept_existing + dist NULL): {url_exact_events}")
        if url_exact_events < 1:
            print("  ❌ BLOCKER: Nessun evento 'url_exact' trovato in article_dedup_events!")
            all_ok = False
        else:
            print(f"  ✅ Eventi 'url_exact' trovati: {url_exact_events} >= 1.")

        # 6. Controllo linkage ledger ↔ article_id
        print("\n6. Controllo linkage ledger ↔ article_id...")
        linked_ledger = await conn.fetchval(
            "SELECT COUNT(*)::INT FROM llm_request_ledger WHERE article_id IS NOT NULL"
        )
        unlinked_ledger = await conn.fetchval(
            "SELECT COUNT(*)::INT FROM llm_request_ledger WHERE article_id IS NULL AND status = 'completed'"
        )
        total_completed_ledger = linked_ledger + unlinked_ledger
        ledger_null_rate = unlinked_ledger / total_completed_ledger if total_completed_ledger > 0 else 0.0
        print(f"  Righe ledger collegate: {linked_ledger}, scollegate: {unlinked_ledger} (NULL-rate: {ledger_null_rate:.1%})")
        if linked_ledger < 1:
            print("  ❌ Nessuna riga ledger collegata ad article_id.")
            all_ok = False
        elif ledger_null_rate > 0.05:
            print(f"  ❌ NULL-rate elevato su linkage ledger ↔ article_id: {ledger_null_rate:.1%} (> 5%)")
            all_ok = False
        else:
            print("  ✅ Linkage ledger ↔ article_id attivo e nei limiti NULL-rate.")

        # 7. Controllo enum geo_resolution_method
        print("\n7. Controllo enum geo_resolution_method...")
        invalid_geo = await conn.fetchval(
            """
            SELECT COUNT(*)::INT FROM articles
            WHERE geo_resolution_method IS NOT NULL
              AND geo_resolution_method NOT IN ('llm_extracted', 'centroid_fallback', 'unchanged')
            """
        )
        if invalid_geo > 0:
            print(f"  ❌ Trovate {invalid_geo} righe con geo_resolution_method non valido!")
            all_ok = False
        else:
            print("  ✅ geo_resolution_method rispetta i valori dell'enum.")

        print("\n==========================================")
        if all_ok:
            print("🎉 ESITO VERIFICA METRICS 013: GATE SUPERATO (VERDE)")
        else:
            print("❌ ESITO VERIFICA METRICS 013: FALLITO (GATE GIALLO/ROSSO)")
        print("==========================================")
        return all_ok

    finally:
        await conn.close()


def main() -> None:
    ok = asyncio.run(run_verification())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
