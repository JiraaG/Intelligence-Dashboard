# Agent prompt — Metrics 013 micro-fix GATE (YELLOW → GREEN vero)

> **Stato: ACTIVE** — post-audit chiusura 2026-07-22.  
> **Contesto:** Metrics 013 funzionalmente OK (`e248f29`); GATE dichiarato VERDE è **overclaim** su verify/STATUS/image.  
> **Piano:** [`../../complete/plan_impl_fase_metrics_013.md`](../../complete/plan_impl_fase_metrics_013.md)  
> **Branch:** `feature/upgrades`  
> **Non rifare** l’intera fase 013.

---

## Come usare

1. Chat **Agent** su `feature/upgrades`.
2. Incolla il blocco **PROMPT**.
3. Scope ristretto: verify + rebuild + STATUS + ri-prova live. Niente UI, niente re-design metrics.

---

## PROMPT (incolla in Agent mode)

```text
# Task — Metrics 013 micro-fix: allineare GATE “VERDE” allo strict verify reale

## Ruolo
Pipeline engineer Radar. La Fase Metrics 013 è **funzionalmente shipped** (commit tipico `e248f29` su `feature/upgrades`): denorm, url_exact≥1, API `/api/metrics/*`, Fix A/C, pytest 229 OK.

Un audit ha classificato il closeout come **YELLOW**, non GREEN pulito, perché:
1. `verify_metrics_013.py` (HEAD) applica NULL-rate ledger **globale** su tutti i `completed` storici → ~96% unlinked pre-013 → exit 1 se eseguito strict su DB live.
2. L’immagine `radar-worker` al momento dell’audit poteva ancora girare uno script **più soft** (exit 0 “GATE SUPERATO”) ≠ HEAD.
3. `plan-audit/STATUS.md` incoerente: riga Metrics = GATE VERDE, ma header/residui ancora “impl pending” / link `active/plan_impl_fase_metrics_013.md`.

Obiettivo: micro-fix + rebuild + verify live exit 0 **onesto** + STATUS igienizzato + commit. Non riscrivere Metrics 013.

## Autorità
- SoT: `plan-audit/complete/plan_impl_fase_metrics_013.md` §8 (soglie su pezzi **post-013 / recenti**, non storico intero)
- Evidence audit: url_exact=9, denorm completi=69, none/inserted_new=69, pytest 229, Fix A/C OK
- Skills: `radar-docker-ops`, `radar-quota-ledger` (solo se tocchi ledger semantics)
- Sidebar freeze; no UI; no `--purge-all`; non stageare `.env`

## Fix obbligatori

### F1 — `verify_metrics_013.py` (ledger NULL-rate scoped)
Oggi (HEAD) qualcosa tipo:
- `linked` = COUNT article_id IS NOT NULL (tutto lo storico)
- `unlinked` = completed AND article_id IS NULL (include pre-013)
- fallisce se unlinked/(linked+unlinked) > 5%

**Correggi:**
- NULL-rate ledger solo su subset **post-strumentazione**, es. uno di (preferisci il più stretto sensato e documentalo nel docstring):
  - `miniflux_entry_id IS NOT NULL AND created_at > NOW() - INTERVAL '48 hours'`
  - oppure `miniflux_entry_id IS NOT NULL AND article_id IS NOT NULL` come linked, e unlinked = `miniflux_entry_id IS NOT NULL AND article_id IS NULL AND status IN ('completed','failed')` nella stessa finestra
- Mantieni: linked ≥ 1 nel subset
- Mantieni soglie già buone:
  - ≥12 articoli denorm completi (lane + latency>0 + model)
  - NULL-rate &lt;5% su **quel subset articles** per feed_id / classified_by_model / dedup_kind
  - ≥1 url_exact (kept_existing + cosine_distance IS NULL)
  - schema columns + geo enum
- exit 0 solo se tutti passano; altrimenti exit 1
- Non dichiarare VERDE se url_exact=0

### F2 — Rebuild worker = HEAD
```bash
cd radar && docker compose up -d --build radar-worker
# o up -d --build se serve coerenza backend
```
Verifica che lo script nel container sia quello HEAD (stesso check scoped / stesso conteggio linee o checksum path).

### F3 — STATUS.md igiene
- Header quadro: Metrics 013 **COMPLETE / GATE VERDE** (non “ACTIVE docs / impl pending”)
- Rimuovi/aggiorna residui che linkano `active/plan_impl_fase_metrics_013.md`
- Conferma riga tabella complete corretta
- Aggiorna `plan-audit/README.md` / `active/README.md` se ancora citano Metrics come active impl
- Checklist §10 del piano complete: marca item verify se applicabile

### F4 — (opz. minimo) Commento walkthrough
Se esiste nota GATE nel piano complete, aggiungi 1 riga: verify ledger scoped a post-013/recente; image rebuildata.

## Verifica obbligatoria (in ordine)

### V1 — unit
```bash
# preferisci nel container o .venv allineato
pytest -m "not live" -q
```
Deve restare verde (229+ se hai aggiunto test; non rompere Fix C).

### V2 — rebuild + script parity
```bash
cd radar && docker compose up -d --build
docker compose exec -T radar-worker python -c "import inspect, app.scripts.verify_metrics_013 as m; print(m.__file__); print(inspect.getsource(m.run_verification)[:500])"
```
Conferma testo scoped (miniflux_entry_id / finestra), non rate globale cieco.

### V3 — verify live
```bash
docker compose exec -T radar-worker python -m app.scripts.verify_metrics_013
echo EXIT:$?
```
**PASS = exit 0** con output che mostra:
- denorm ≥12
- url_exact ≥1
- ledger NULL-rate sul **subset scoped** &lt;5% (o linked ok)
Se fallisce solo per dati, diagnostica; non allentare di nuovo le soglie articles/url_exact.

### V4 — spot SQL/API (evidenza)
```sql
SELECT COUNT(*) FROM article_dedup_events
WHERE dedup_kind='url_exact' AND action_taken='kept_existing' AND cosine_distance IS NULL;

SELECT COUNT(*) FROM articles
WHERE classification_lane IS NOT NULL AND pipeline_latency_ms > 0 AND classified_by_model IS NOT NULL;

SELECT dedup_kind, dedup_action, COUNT(*) FROM articles
WHERE dedup_kind IS NOT NULL GROUP BY 1,2 ORDER BY 3 DESC;
```
```bash
curl -sS "http://localhost/api/metrics/summary" | head -c 1500
curl -sS "http://localhost/api/metrics/dedup" | head -c 800
```
url_exact_count API ≥ 1.

### V5 — log
```bash
docker compose logs radar-worker --tail 100 | grep -E 'ERROR|Traceback' || true
```

## Fuori scope
- Re-implementare ClassificationResult / API metrics / migration 013
- UI FinOps, sidebar, Wave 2, --purge-all, backfill storico massivo article_id su ledger vecchio
- Allentare soglia url_exact o ≥12 articles

## Done when
- [ ] F1 verify scoped + exit corretto
- [ ] F2 worker image = HEAD
- [ ] F3 STATUS/README igienizzati
- [ ] V1 pytest verde
- [ ] V3 verify exit 0 (strict onesto)
- [ ] V4 url_exact + denorm confermati
- [ ] Commit dettagliato (solo file touchati; no `.env`)
- Messaggio commit es.: `fix(metrics): scope verify_metrics_013 ledger NULL-rate to post-013 window`

## Deliverable
Diff + exit code verify + snippet SQL/API + commit hash + conferma STATUS coerente.

Parti da F1. Non riaprire il piano Metrics come ACTIVE.
```

---

## Nota per te (PO)

Dopo questa chat, un audit di conferma deve vedere: **stesso** verify in repo e in container, exit 0, STATUS senza crumb “impl pending”.
