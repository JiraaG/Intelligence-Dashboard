# Audit backend — Radar Informativo Globale

> **Data:** 2026-07-15  
> **Scope:** `radar/backend/app/**`, `radar/backend/scripts/**` vs checklist `scratch/backend_rules.md` (81 item)  
> **Metodo:** lettura del codice sorgente reale; nessuna modifica applicativa in questo audit.  
> **Lingua:** italiano (identificatori/codice in English)

---

## Sintesi esecutiva

Il path di produzione (`worker.py` + `classification/` + `commit/` + API Phase 5) è **largamente conforme** alle hard rule su QuotaLedger, CancelledError, dedup pre-Gemini, outbox atomico, schema Pydantic strict e API envelope.

Restano **gap reali**:

| Priorità | Conteggio | Focus |
|----------|----------:|-------|
| **P0** | **1** | Mark-read Miniflux sul path duplicato senza verifica vault/outbox `completed` |
| **P1** | **5** | `quote_plus` assente; race dedup multi-consumer; mark-read post-`completed` non ritentabile; script rotti (`ClassificationClient()` / `_wait_for_rate_limit`) |
| **P2** | **4** | Fallback `'Nessuna'` vs `'Nessuno'`; `img` non in ignored-tags; nessun check primo tag; bare `except` negli script diagnostici |

**Script già noti (audit documentazione):** **confermati ancora rotti** — non fixati.

---

## Tabella pass/fail per dominio

| # | Dominio | Items | PASS | FAIL / PARZIALE |
|---|---------|------:|-----:|----------------:|
| 1 | Worker loop / CancelledError / no sleep in finally | 7 | 7 | 0 |
| 2 | QuotaLedger | 9 | 9 | 0 |
| 3 | LLM JSON extraction | 15 | 14 | 1 |
| 4 | Outbox / transactional commit | 7 | 5 | 2 |
| 5 | Deduplicazione pre-Gemini | 3 | 3 | 0 |
| 6 | Caching (durable state) | 4 | 4 | 0 |
| 7 | API contract Phase 5 | 8 | 8 | 0 |
| 8 | ClassificationClient / QuotaLedger injection | 4 | 4\* | 0\* |
| 9 | Exception handling | 6 | 6 | 0 |
| 10 | DATABASE_URL / credential encoding | 6 | 5 | 1 |
| 11 | Altre hard rules | 12 | 11 | 1 |
| | **TOTALE checklist** | **81** | **76** | **5** |

\* Dominio 8: **app di produzione PASS**; gli script sotto `scripts/` violano BE-CC-01/02 (conteggiati come finding separati, non come fail del dominio app).

---

## Finding (FAIL / bug latenti)

### [BE-AUD-001] Mark-read su duplicato senza gate outbox `completed`
- **Priorità:** P0
- **Checklist:** BE-OB-04
- **File e Range Righe:** `radar/backend/app/worker.py#L213-L219`
- **Casistica Rilevata & Rischio:** Se l’URL è già in `articles` ma la proiezione Vault è ancora `pending`/`failed` (o il reconcile del ciclo non ha ancora ripristinato il file), il path duplicato chiama comunque `mark_as_read`. Viola il gate «mark-read solo dopo vault durable»: si può perdere l’entry Miniflux senza Markdown durable, specialmente se `reconcile_outbox` fallisce in parte o l’entry riappare tra commit DB e scrittura Vault.
- **Evidenza (snippet attuale):**
```python
        if is_dup:
            logger.info(
                "Articolo duplicato rilevato: '%s'. Marcatura come letto su Miniflux...",
                title[:50],
            )
            await state.miniflux_client.mark_as_read([entry_id])
            return True
```
- **Codice Correttivo (Diff):**
```diff
@@ process_single_entry @@
-        if is_dup:
-            logger.info(
-                "Articolo duplicato rilevato: '%s'. Marcatura come letto su Miniflux...",
-                title[:50],
-            )
-            await state.miniflux_client.mark_as_read([entry_id])
-            return True
+        if is_dup:
+            async with state.db_sem:
+                async with state.db_pool.acquire() as conn:
+                    outbox_status = await conn.fetchval(
+                        """
+                        SELECT o.status
+                        FROM articles a
+                        LEFT JOIN article_outbox o ON o.article_id = a.id
+                        WHERE a.source_url = $1
+                        """,
+                        source_url,
+                    )
+            if outbox_status == "completed":
+                logger.info(
+                    "Duplicato con vault completed: mark-read Miniflux per '%s'.",
+                    title[:50],
+                )
+                await state.miniflux_client.mark_as_read([entry_id])
+            else:
+                logger.warning(
+                    "Duplicato DB ma outbox status=%r per '%s': skip mark-read; "
+                    "attendo reconcile.",
+                    outbox_status,
+                    title[:50],
+                )
+            return True
```

---

### [BE-AUD-002] `DATABASE_URL` di fallback senza URL-encoding
- **Priorità:** P1
- **Checklist:** BE-DB-05
- **File e Range Righe:** `radar/backend/app/core/config.py#L91-L98`
- **Casistica Rilevata & Rischio:** `POSTGRES_USER` / `POSTGRES_PASSWORD` sono interpolati grezzi. Caratteri `@`, `:`, `/`, `#`, `%` nella password rompono il parser URL di asyncpg → crash all’avvio (API e worker). Stesso pattern in Compose (`DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@...`) se le credenziali non sono già encoded.
- **Evidenza (snippet attuale):**
```python
pg_user = _env_str("POSTGRES_USER", "radar_user") or "radar_user"
pg_pass = _env_str("POSTGRES_PASSWORD", _DEFAULT_PG_PASSWORD) or _DEFAULT_PG_PASSWORD
...
_default_db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
DATABASE_URL = _env_str("DATABASE_URL", _default_db_url) or _default_db_url
```
- **Codice Correttivo (Diff):**
```diff
+from urllib.parse import quote_plus
+
 pg_user = _env_str("POSTGRES_USER", "radar_user") or "radar_user"
 pg_pass = _env_str("POSTGRES_PASSWORD", _DEFAULT_PG_PASSWORD) or _DEFAULT_PG_PASSWORD
 pg_db = _env_str("POSTGRES_DB", "radar_db") or "radar_db"
 pg_host = _env_str("POSTGRES_HOST", "localhost") or "localhost"
 pg_port = _env_str("POSTGRES_PORT", "5432") or "5432"
-_default_db_url = f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
+_default_db_url = (
+    f"postgresql://{quote_plus(pg_user)}:{quote_plus(pg_pass)}"
+    f"@{pg_host}:{pg_port}/{pg_db}"
+)
```

---

### [BE-AUD-003] Race TOCTOU dedup multi-consumer → doppia chiamata Gemini
- **Priorità:** P1
- **Checklist:** BE-DD-01 / BE-DD-03 (latente); BE-HR-08
- **File e Range Righe:** `radar/backend/app/worker.py#L208-L251` (+ `WORKER_ENTRY_CONCURRENCY` default 4)
- **Casistica Rilevata & Rischio:** Due consumer possono passare `is_article_duplicate` sullo stesso `source_url` prima di entrambi i commit. Entrambi chiamano Gemini; il secondo fa `ON CONFLICT DO NOTHING`. Spreco di quota RPD/RPM e rischio di sovrascrivere `miniflux_entry_id` sull’outbox (`COALESCE(EXCLUDED...)`) lasciando un entry_id non mark-read finché non ricade sul path duplicato.
- **Evidenza (snippet attuale):**
```python
        async with state.db_sem:
            async with state.db_pool.acquire() as conn:
                is_dup = await is_article_duplicate(conn, source_url)
        ...
        async with state.gemini_sem:
            extracted_article = await state.classification_client.classify_article(...)
        ...
                article_id = await commit_article_to_db(...)  # ON CONFLICT DO NOTHING
```
- **Codice Correttivo (Diff):**
```diff
# Opzione A (semplice): serializzare classify+commit per URL
# Opzione B (consigliata): advisory lock per-hash(URL) intorno a dedup→gemini→commit

+        url_lock_key = int(hashlib.sha256(source_url.encode()).hexdigest()[:15], 16)
+        async with state.db_pool.acquire() as lock_conn:
+            await lock_conn.execute("SELECT pg_advisory_lock($1)", url_lock_key)
+            try:
+                is_dup = await is_article_duplicate(lock_conn, source_url)
+                if is_dup:
+                    ...  # gate outbox completed come in BE-AUD-001
+                    return True
+                # sanitize + classify + commit sotto lo stesso lock
+                ...
+            finally:
+                await lock_conn.execute("SELECT pg_advisory_unlock($1)", url_lock_key)
```

---

### [BE-AUD-004] Mark-read Miniflux dopo `completed` non ritentabile
- **Priorità:** P1
- **Checklist:** BE-OB-04 (completamento parziale)
- **File e Range Righe:** `radar/backend/app/commit/outbox.py#L170-L185`
- **Casistica Rilevata & Rischio:** Dopo `_mark_completed`, un fallimento di `mark_as_read` viene solo loggato. Le righe `completed` non rientrano in `reconcile_outbox` (`WHERE status IN ('pending', 'failed')`). L’entry resta unread → re-fetch → path duplicato (oggi mark-read aggressivo; dopo fix BE-AUD-001 dipende da outbox completed → OK, ma solo se il path duplicato resta). Meglio uno stato `vault_done` / flag `miniflux_acked` o coda di retry dedicata.
- **Evidenza (snippet attuale):**
```python
    async with pool.acquire() as conn:
        await _mark_completed(conn, outbox_id)

    entry_id = claimed["miniflux_entry_id"]
    if entry_id is not None and miniflux_client is not None:
        try:
            await miniflux_client.mark_as_read([int(entry_id)])
        except Exception as mark_err:
            logger.warning(
                "Outbox id=%s completed ma mark-read Miniflux fallito (entry_id=%s): %s",
                ...
            )
```
- **Codice Correttivo (Diff):**
```diff
-    async with pool.acquire() as conn:
-        await _mark_completed(conn, outbox_id)
-
-    entry_id = claimed["miniflux_entry_id"]
-    if entry_id is not None and miniflux_client is not None:
-        try:
-            await miniflux_client.mark_as_read([int(entry_id)])
-        except Exception as mark_err:
-            logger.warning(...)
+    entry_id = claimed["miniflux_entry_id"]
+    if entry_id is not None and miniflux_client is not None:
+        try:
+            await miniflux_client.mark_as_read([int(entry_id)])
+        except Exception as mark_err:
+            async with pool.acquire() as conn:
+                await conn.execute(
+                    """
+                    UPDATE article_outbox
+                    SET status = 'completed',
+                        last_error = $2,
+                        updated_at = NOW()
+                    WHERE id = $1
+                    """,
+                    outbox_id,
+                    f"vault_ok mark_read_pending: {mark_err}"[:4000],
+                )
+            # reconcile dedicato: SELECT WHERE status='completed' AND last_error LIKE 'vault_ok mark_read_pending%'
+            return True
+    async with pool.acquire() as conn:
+        await _mark_completed(conn, outbox_id)
```
*(Alternativa più pulita: colonna `miniflux_marked_at TIMESTAMPTZ NULL` + reconcile delle completed con `miniflux_marked_at IS NULL`.)*

---

### [BE-AUD-005] Script produzione: `ClassificationClient()` senza pool/quota
- **Priorità:** P1
- **Checklist:** BE-CC-01
- **File e Range Righe:** `radar/backend/scripts/test_production_pipeline.py#L327`; `radar/backend/scripts/diagnostics/test_rate_limiter.py#L17`; `radar/backend/scripts/diagnostics/test_500.py#L11`
- **Casistica Rilevata & Rischio:** Il costruttore richiede `pool` o `quota` (`ValueError`). Gli script diagnostici/live crashano all’avvio. Anche `test_integration_live.py` importa `stress_test_rate_limiter` dallo script rotto → live test rate-limiter non utilizzabile. **Bug già noto in documentazione: CONFERMATO non fixato.**
- **Evidenza (snippet attuale):**
```python
        classification = ClassificationClient()
```
- **Codice Correttivo (Diff):**
```diff
-        classification = ClassificationClient()
+        pool = await asyncpg.create_pool(DATABASE_URL)
+        try:
+            classification = ClassificationClient(pool=pool)
+            await test_external_connections(miniflux, classification)
+            ...
+        finally:
+            await pool.close()
```
*(Per diagnostici one-shot: mock `QuotaLedger` / `AsyncMock` come in `test_integration_live._live_classification_client`.)*

---

### [BE-AUD-006] Script: chiamata a `_wait_for_rate_limit` rimosso dal client
- **Priorità:** P1
- **Checklist:** BE-CC-02 / BE-QL-07
- **File e Range Righe:** `radar/backend/scripts/test_production_pipeline.py#L296-L297`; `radar/backend/scripts/diagnostics/test_rate_limiter.py#L12`
- **Casistica Rilevata & Rischio:** `AttributeError` a runtime. Il gate ufficiale è `QuotaLedger.reserve` / `release`. **Bug già noto: CONFERMATO non fixato.** Il test live `test_live_rate_limiter_throttling` delega a questa funzione → fallisce sempre se eseguito.
- **Evidenza (snippet attuale):**
```python
    async def limiter_worker(worker_id: int) -> None:
        await classification._wait_for_rate_limit()
```
- **Codice Correttivo (Diff):**
```diff
     async def limiter_worker(worker_id: int) -> None:
-        await classification._wait_for_rate_limit()
+        rid = await classification.quota.reserve(
+            estimated_tokens=1, purpose="stress_spacing"
+        )
+        await classification.quota.release(rid)
         acq_time = time.time()
```

---

### [BE-AUD-007] Fallback usa `'Nessuna'` invece di `'Nessuno'`
- **Priorità:** P2
- **Checklist:** BE-LLM-05
- **File e Range Righe:** `radar/backend/app/classification/validator.py#L227-L231`
- **Casistica Rilevata & Rischio:** SoT richiede vuoti → esattamente `'Nessuno'`. Il fallback scrive `'Nessuna'` per `companies_involved` / `infrastructural_entities`. `parse_csv_list` tratta entrambi come vuoti, quindi non rompe il commit, ma viola il contratto stringa e può confondere FE/Vault/debug.
- **Evidenza (snippet attuale):**
```python
        companies_involved="Nessuna",
        tags="Infrastrutture",
        primary_category="Infrastrutture",
        sentiment="Neutrale",
        infrastructural_entities="Nessuna",
```
- **Codice Correttivo (Diff):**
```diff
-        companies_involved="Nessuna",
+        companies_involved="Nessuno",
         tags="Infrastrutture",
         primary_category="Infrastrutture",
         sentiment="Neutrale",
-        infrastructural_entities="Nessuna",
+        infrastructural_entities="Nessuno",
```

---

### [BE-AUD-008] `img` assente da `content_ignored_tags` nel parser HTML
- **Priorità:** P2
- **Checklist:** BE-HR-03
- **File e Range Righe:** `radar/backend/app/extraction/parser.py#L22-L25`
- **Casistica Rilevata & Rischio:** `video`/`audio`/`noscript`/`meta` sono ignorati (contenuto interno); `img` no. I tag vengono comunque rimossi dal parser, e `alt` non è testo HTML; però markup non standard (`<img>fallback</img>`) lascerebbe testo, e la checklist elenca `img` esplicitamente. Il test `test_strip_html_tags_media_tags` passa per attributi, non per contenuto interno img.
- **Evidenza (snippet attuale):**
```python
        self.content_ignored_tags = {
            "script", "style", "iframe", "svg", "noscript", "meta",
            "video", "audio", "embed", "object"
        }
```
- **Codice Correttivo (Diff):**
```diff
         self.content_ignored_tags = {
             "script", "style", "iframe", "svg", "noscript", "meta",
-            "video", "audio", "embed", "object"
+            "video", "audio", "embed", "object", "img", "picture", "source"
         }
```

---

### [BE-AUD-009] Nessuna validazione che il primo tag == `primary_category`
- **Priorità:** P2
- **Checklist:** BE-LLM-14
- **File e Range Righe:** `radar/backend/app/classification/prompts.py#L14-L15`; `radar/backend/app/classification/validator.py#L104-L120` (manca model/field validator)
- **Casistica Rilevata & Rischio:** Istruzione solo nel system prompt. Output Gemini può passare `strict` con primo tag diverso dalla primary → inconsistenza tags/junction DB e filtri FE.
- **Evidenza (snippet attuale):** Prompt impone la regola; schema ha solo `description`, nessun `@model_validator`.
- **Codice Correttivo (Diff):**
```diff
+    @model_validator(mode="after")
+    def first_tag_matches_primary(self) -> Self:
+        first = (self.tags.split(",")[0].strip() if self.tags else "")
+        if first.lower() in {"nessuno", "nessuna", "none", ""}:
+            raise ValueError("tags deve iniziare con primary_category")
+        if first != self.primary_category:
+            raise ValueError(
+                f"primo tag {first!r} != primary_category {self.primary_category!r}"
+            )
+        return self
```

---

### [BE-AUD-010] Bare `except:` negli script diagnostici Gemini
- **Priorità:** P2
- **Checklist:** BE-EX-02 (script; non path produzione)
- **File e Range Righe:** `radar/backend/scripts/diagnostics/test_500_bot.py#L7-L11`; analoghi in `test_500_debug.py`, `test_string_lists.py`
- **Casistica Rilevata & Rischio:** Swallow totale degli errori di lettura prompt → fallback silenzioso a system prompt banale; diagnostica fuorviante.
- **Evidenza (snippet attuale):**
```python
try:
    with open('classification/prompts.py', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().split('SYSTEM_PROMPT = ')[1].strip('\"\"\"\n')
except:
    SYSTEM_PROMPT = "Sei un assistente."
```
- **Codice Correttivo (Diff):**
```diff
-except:
+except OSError as exc:
+    logging.warning("Impossibile caricare SYSTEM_PROMPT: %s", exc)
     SYSTEM_PROMPT = "Sei un assistente."
```

---

## Checklist PASS (breve)

### 1. Worker loop
- **BE-WL-01** — `run_pipeline_loop` / `run_pipeline_cycle` in `worker.py`; `main.py` API-only.
- **BE-WL-02** — `CancelledError` re-raised in loop, consumer, classify, shutdown path.
- **BE-WL-03** — `asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)` fuori da `finally` di shutdown.
- **BE-WL-04** — nessun `time.sleep` nel path async app.
- **BE-WL-05** — `except Exception` a livello ciclo con `exc_info=True`, poi sleep e nuovo ciclo.
- **BE-WL-06** — advisory lock session-level + coda bounded + Compose un solo `radar-worker`.
- **BE-WL-07** — entrypoint `python -m app.worker`; nessun ingest nel lifespan FastAPI.

### 2. QuotaLedger
- **BE-QL-01…09** — `reserve` prima di ogni tentativo (anche validation retry); `complete`/`fail`/`release` su `reservation_id`; monotonic spacing; RPD half-open `RADAR_TIME_ZONE`; Retry-After su 429; ledger durable `003_quota_ledger.sql`; `wait_for` + `GEMINI_REQUEST_TIMEOUT`.

### 3. LLM JSON
- **BE-LLM-01…04, 06…13, 15** — `google-genai`, system prompt senza CoT, `<untrusted_article>`, `strict`+`extra=forbid`, Literal 10 categorie / sentiment, `build_gemini_response_schema()`, mime JSON + `model_validate_json`, truncazione `[:4000]`, fallback lat/lon/XX, title max 120, italiano IT nel prompt.
- **BE-LLM-05** — tipi `str` CSV OK; **fallback stringa vuota vedi FAIL BE-AUD-007**.
- **BE-LLM-14** — istruzione prompt OK; **validazione runtime assente → BE-AUD-009**.

### 4. Outbox
- **BE-OB-01** — overwrite `source_url` / `published_at` da Miniflux in `process_single_entry`.
- **BE-OB-02** — article + outbox in una sola `conn.transaction()`.
- **BE-OB-03** — tmp → fsync → `os.replace` + `PermanentFileLock`; `completed` post-write.
- **BE-OB-05** — reconcile all’inizio di ogni ciclo (dopo leadership).
- **BE-OB-06** — default vault `/app/vault`.
- **BE-OB-07** — containment `relative_to(vault_root)` + SHA-256[:16]; mkdir on write.
- **BE-OB-04** — happy path OK; **path duplicato / retry mark-read → FAIL** (BE-AUD-001, BE-AUD-004).

### 5–6. Dedup / cache
- **BE-DD-01…03** — `SELECT EXISTS` prima di Gemini; skip senza classify.
- **BE-CA-01…04** — dedup SQL; ledger durable; reserve per tentativo; `.dockerignore` esclude venv/pycache.

### 7. API Phase 5
- **BE-API-01…08** — `/api/map-summary` aggregato; `/api/articles` envelope + limit≤100; migration `007`; `main.py` API-only; no `CORS *`; `/health/live` vs `/ready`; Compose uvicorn workers=1 / worker command corretto.

### 8. ClassificationClient (produzione)
- **BE-CC-01…04** — `ClassificationClient(pool=...)` nel worker; protocollo quota; key da env; retry classificato. *(Script: FAIL separati.)*

### 9. Exception / logging
- **BE-EX-01…06** — tre livelli; no swallow CancelledError operativo; fallback Gemini; logger centralizzato; `makedirs`+`RotatingFileHandler` in `try/except OSError` con console sempre attiva. Nessun `print()` in `app/` produzione.

### 10. DB / HTTP
- **BE-DB-01…04, 06** — dotenv/env; no secret in source; asyncpg + SQL `$n`; httpx async. **BE-DB-05 FAIL** (BE-AUD-002).

### 11. Hard rules
- **BE-HR-01** — solo `>=` in `app/requirements.txt`.
- **BE-HR-02** — no TODO/FIXME/HACK di produzione lasciati.
- **BE-HR-04…12** — type hints pubbliche, layer modulari, async sleep, untrusted input, bound coda/byte, ingest solo worker, vault mkdir on demand, fail-fast production secrets.
- **BE-HR-03** — sanitize stdlib OK; **img vedi BE-AUD-008**.

---

## Nota script noti (conferma stato)

| Script | Bug atteso | Stato audit 2026-07-15 |
|--------|------------|------------------------|
| `scripts/test_production_pipeline.py` | `ClassificationClient()` + `_wait_for_rate_limit` | **CONFERMATO ROTTO** (L327, L297) |
| `scripts/diagnostics/test_rate_limiter.py` | stesso | **CONFERMATO ROTTO** (L17, L12) |
| `scripts/diagnostics/test_500.py` | `ClassificationClient()` | **CONFERMATO ROTTO** (L11) |
| `scripts/diagnostics/test_500_*.py`, `test_exact.py`, `test_no_schema.py`, `test_string_lists.py` | schema legacy `reasoning`/`List[str]`, bare except, path import fragili | **Obsoleti / diagnostici non allineati** allo schema SoT attuale (non usati dal worker) |
| `scripts/seed_perf_articles.py` | — | **OK** (asyncpg + `DATABASE_URL`, no ClassificationClient) |

Il test live `app/tests/test_integration_live.py::test_live_rate_limiter_throttling` dipende ancora da `stress_test_rate_limiter` dello script rotto → **indirettamente rotto**.

---

## Conteggi finding (report)

| Priorità | ID finding |
|----------|------------|
| **P0** (1) | BE-AUD-001 |
| **P1** (5) | BE-AUD-002, BE-AUD-003, BE-AUD-004, BE-AUD-005, BE-AUD-006 |
| **P2** (4) | BE-AUD-007, BE-AUD-008, BE-AUD-009, BE-AUD-010 |

**Totale finding:** 10  
**Checklist items FAIL espliciti:** ~5 (OB-04, DB-05, LLM-05 soft, HR-03 soft, CC via scripts)  
**Checklist items PASS:** 76 / 81 (con le nuance sopra)

---

## Raccomandazione priorità di remediation

1. **P0** — Gate mark-read sul path duplicato (BE-AUD-001).  
2. **P1** — `quote_plus` (BE-AUD-002); lock per-URL o serializzazione (BE-AUD-003); retry mark-read (BE-AUD-004); allineare/riparare o deprecare gli script live (BE-AUD-005/006).  
3. **P2** — stringhe fallback, parser `img`, validator primo tag, cleanup diagnostici.
