"""Script di verifica & baseline M2 FinOps LLM Wave A.

Esegue query readonly su PostgreSQL per raccogliere le metriche di baseline e post-deploy.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
import asyncpg

from app.core.config import DATABASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("radar.scripts.verify_llm_finops_wave_a")


async def run_baseline_metrics(conn: asyncpg.Connection, days: int = 7) -> dict:
    logger.info("Esecuzione baseline FinOps (finestra: %d giorni)...", days)
    
    # 1. Token split classify / quality:compare
    token_rows = await conn.fetch(
        """
        SELECT
          provider,
          purpose,
          COUNT(*)::INT AS n,
          AVG(prompt_tokens)::INT AS avg_prompt,
          PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prompt_tokens)::INT AS p50_prompt,
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY prompt_tokens)::INT AS p95_prompt,
          AVG(completion_tokens)::INT AS avg_completion,
          PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY completion_tokens)::INT AS p95_completion,
          SUM(COALESCE(cached_prompt_tokens, 0))::BIGINT AS sum_cached,
          SUM(COALESCE(prompt_tokens, 0))::BIGINT AS sum_prompt
        FROM llm_request_ledger
        WHERE status = 'completed'
          AND created_at >= NOW() - make_interval(days => $1::int)
        GROUP BY 1, 2
        ORDER BY n DESC
        """,
        days,
    )
    
    # 2. Status & errors
    status_rows = await conn.fetch(
        """
        SELECT status, COALESCE(error_code, 'NONE') AS error_code, COUNT(*)::INT AS n
        FROM llm_request_ledger
        WHERE created_at >= NOW() - make_interval(days => $1::int)
        GROUP BY 1, 2
        ORDER BY n DESC
        """,
        days,
    )

    # 3. Articles escalation
    esc_row = await conn.fetchrow(
        """
        SELECT
          COUNT(*)::INT AS articles,
          COUNT(*) FILTER (WHERE was_escalated)::INT AS escalated,
          ROUND(100.0 * COUNT(*) FILTER (WHERE was_escalated) / NULLIF(COUNT(*), 0), 2)::FLOAT AS escalated_pct
        FROM articles
        WHERE created_at >= NOW() - make_interval(days => $1::int)
        """,
        days,
    )

    # 4. Dedup events
    dedup_rows = await conn.fetch(
        """
        SELECT COALESCE(dedup_kind, 'unknown') AS dedup_kind, COALESCE(action_taken, 'unknown') AS action_taken, COUNT(*)::INT AS n
        FROM article_dedup_events
        WHERE created_at >= NOW() - make_interval(days => $1::int)
        GROUP BY 1, 2
        ORDER BY n DESC
        """,
        days,
    )

    return {
        "token_split": [dict(r) for r in token_rows],
        "status_split": [dict(r) for r in status_rows],
        "escalation": dict(esc_row) if esc_row else {"articles": 0, "escalated": 0, "escalated_pct": 0.0},
        "dedup": [dict(r) for r in dedup_rows],
    }


async def main() -> None:
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as exc:
        logger.error("Impossibile connettersi al DB (%s): %s", DATABASE_URL, exc)
        sys.exit(1)

    try:
        res = await run_baseline_metrics(conn, days=7)
        print("\n=== BASELINE M2 FINOPS (ultimi 7 giorni) ===")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        print("\n--- TOKEN SPLIT ---")
        for r in res["token_split"]:
            cache_rate = (r['sum_cached'] / r['sum_prompt'] * 100) if r['sum_prompt'] > 0 else 0.0
            print(f"Provider: {r['provider']} | Purpose: {r['purpose']} | Count: {r['n']} | Prompt avg/p50/p95: {r['avg_prompt']}/{r['p50_prompt']}/{r['p95_prompt']} | Comp avg/p95: {r['avg_completion']}/{r['p95_completion']} | Cached sum/rate: {r['sum_cached']} ({cache_rate:.2f}%)")

        print("\n--- STATUS / ERRORS ---")
        for r in res["status_split"]:
            print(f"Status: {r['status']} | ErrorCode: {r['error_code']} | Count: {r['n']}")

        print("\n--- ARTICLES ESCALATION ---")
        esc = res["escalation"]
        print(f"Total articles: {esc['articles']} | Escalated: {esc['escalated']} ({esc['escalated_pct']}%)")

        print("\n--- DEDUP ACTIONS ---")
        for r in res["dedup"]:
            print(f"Kind: {r['dedup_kind']} | Action: {r['action_taken']} | Count: {r['n']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
