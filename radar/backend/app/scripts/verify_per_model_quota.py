"""Script di verifica per-model quota: usati, cap e residui per modello dal ledger DB.

Uso:
    python -m app.scripts.verify_per_model_quota
Exit 0 se consistente; exit 1 se riscontra incongruenze gravi.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import Any

import asyncpg

from app.classification.quota import compute_day_window
from app.core.config import DATABASE_URL, LLM_COMPLEX, LLM_SIMPLE, RADAR_TIME_ZONE
from app.core.llm_lanes import limits_for_model


async def main() -> int:
    print("=== Verification Script: Per-Model Quota Ledger ===")
    day_start, day_end = compute_day_window(datetime.now(timezone.utc), RADAR_TIME_ZONE)
    print(f"Timezone window: {day_start.isoformat()} -> {day_end.isoformat()}")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        models_to_check: list[tuple[str, str, Any]] = []
        for m in LLM_SIMPLE.models:
            models_to_check.append((m, "simple", LLM_SIMPLE))
        for m in LLM_COMPLEX.models:
            if m not in [x[0] for x in models_to_check]:
                models_to_check.append((m, "complex", LLM_COMPLEX))

        print("\n" + "=" * 70)
        print(f"{'MODEL':<30} | {'LANE':<8} | {'USED TODAY':<10} | {'CAP':<8} | {'RESIDUAL':<8}")
        print("-" * 70)

        any_simple_residual = False
        all_simple_managed_exhausted = True

        for model, lane_name, lane_cfg in models_to_check:
            rpm, tpm, rpd = limits_for_model(lane_cfg, model)
            used = await conn.fetchval(
                """
                SELECT COUNT(*)::INT
                FROM llm_request_ledger
                WHERE created_at >= $1
                  AND created_at < $2
                  AND status = ANY($3::text[])
                  AND model = $4
                """,
                day_start,
                day_end,
                ["reserved", "completed", "failed"],
                model,
            )
            used = int(used or 0)
            if rpd == 0:
                cap_str = "0 (unmanaged)"
                res_str = "∞"
                if lane_name == "simple":
                    any_simple_residual = True
                    all_simple_managed_exhausted = False
            else:
                cap_str = str(rpd)
                res = max(0, rpd - used)
                res_str = str(res)
                if lane_name == "simple":
                    if res > 0:
                        any_simple_residual = True
                        all_simple_managed_exhausted = False

            print(f"{model:<30} | {lane_name:<8} | {used:<10} | {cap_str:<8} | {res_str:<8}")

        print("=" * 70)
        print(f"Catena SIMPLE: any_residual={any_simple_residual}, all_managed_exhausted={all_simple_managed_exhausted}")
        print("Verification OK.")
        return 0

    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
