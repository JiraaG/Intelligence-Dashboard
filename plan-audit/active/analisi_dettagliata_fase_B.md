# Analisi Successiva Dettagliata — Fase B (Risks & Edge Cases)

Questo documento fornisce un'analisi tecnica profonda (Deep Dive) del piano architetturale per la Fase B (Webhook & SSE). L'obiettivo è validare le scelte architetturali analizzando potenziali vulnerabilità, race condition, colli di bottiglia prestazionali e il comportamento in scenari di degrado (graceful degradation).

---

## 1. Analisi Concorrenza Database e Prevenzione Starvation

### Il Problema del Pool `asyncpg` con LISTEN
La direttiva `LISTEN` in PostgreSQL richiede che la connessione rimanga permanentemente aperta e bloccata in attesa di eventi. Se implementassimo i listener asincroni prelevando una connessione dal pool (`async with pool.acquire() as conn:`), sottrarremmo permanentemente slot utili al pool. Nel backend FastAPI (che di default può avere un pool limitato, es. 10-20 connessioni), se 10 client SSE attivassero un listener dal pool, si verificherebbe una **Pool Starvation**, bloccando l'intero applicativo (`TimeoutError` su `acquire`).

### Mitigazione Adottata nel Piano
Il piano impone l'uso di **connessioni dedicate bypassando il pool** per tutti i task di ascolto:
```python
# Utilizzo di connessione autonoma, non dal pool
conn = await asyncpg.connect(DATABASE_URL)
await conn.add_listener("channel_name", callback)
```
- Nel **Worker**, la connessione dedicata previene interferenze con i semafori `DB_CONCURRENCY`.
- Nel **Backend FastAPI**, viene utilizzata **una singola connessione dedicata globale** nel `lifespan` (il `backend_article_listener`) che fa da multiplexer e instrada i messaggi tramite `SSEBroadcastManager` a tutte le code dei client connessi, azzerando il costo per-client sul database. Anche con 1000 client SSE connessi, verrà mantenuta solo **1 connessione `LISTEN`** verso PostgreSQL.

---

## 2. Resilienza Rete e Sicurezza Webhook

### Il Problema dei Webhook Persi o Malformati
In una tipica architettura event-driven, se il webhook invia il contenuto dell'articolo e il backend lo elabora direttamente, la perdita di un pacchetto HTTP o un riavvio del demone causerebbe la perdita silente dell'articolo (Drop Loss). Inoltre, Miniflux potrebbe inviare webhook multipli ravvicinati (es. feed batch).

### Sicurezza e Prevenzione DoS (HMAC)
Senza validazione, un malintenzionato potrebbe colpire `/api/webhooks/miniflux` per sovraccaricare il database di sveglie a vuoto (DoS).
La **Mitigazione Adottata** è il calcolo dell'HMAC-SHA256 del payload crudo (raw body) utilizzando `MINIFLUX_WEBHOOK_SECRET` e il confronto sicuro (`hmac.compare_digest`) contro l'header inviato da Miniflux `X-Miniflux-Signature`.

### Disaccoppiamento del Payload
L'endpoint `/api/webhooks/miniflux` adotta un pattern **Trigger-Only (Disaccoppiamento del Payload)**.
1. **Deduplicazione Implicita:** Se arrivano 10 webhook validi in un secondo, il worker si sveglia, avvia `run_pipeline_cycle(state)`, e preleva tutti gli articoli non letti in un singolo batch (`fetch_unread_entries`).
2. **Recupero Perdite (Self-Healing):** Se il webhook viene perso per un partizionamento di rete, il worker ha comunque l'attesa massima limitata a `WORKER_POLL_INTERVAL_SECONDS` (es. 15 minuti) garantita dal comando `asyncio.wait_for`. Questo funge da rete di salvataggio.

---

## 3. Race Conditions Frontend (State.Service.ts)

### Il Conflitto tra UI Ottimistica e Soft Refresh
Nel frontend Angular, quando un utente clicca il pulsante "Segna come letto" o "Salva", il metodo `toggleReadStatus` o `toggleSavedStatus` aggiorna *immediatamente* la UI in modo ottimistico prima della risposta del server.
Cosa succede se, **durante il millisecondo** in cui la patch API è in volo, il frontend riceve un evento SSE che fa scattare il `Soft Refresh`?
Il Soft Refresh esegue `loadCountryArticles()`, che ricarica gli articoli dal DB. Poiché l'update ottimistico non è ancora committato su DB, il server restituirebbe l'articolo con il vecchio stato, causando un fastidioso sfarfallio (flicker visivo) della UI che torna indietro.

### Mitigazione Adottata nel Piano
Nel `state.service.ts` esiste già un pattern di **Versioning delle Mutazioni** (`readMutationVersion.get(articleId)`). 
Per irrobustire ulteriormente l'UX durante il Soft Refresh, è necessario assicurare che:
- La lista sostituita nel Signal `detailArticles` mantenga l'ID degli articoli in modo che Angular usi il Change Detection basato su identità.
- Lapura sostituzione dell'array è considerata accettabile data la velocità delle transazioni locali, e il framework gestisce nativamente la non-distruzione del DOM se la *Reference* (via `trackBy` / identità object) non cambia radicalmente l'HTML.

---

## 4. Comportamento dei Proxy (Nginx) e Timeout SSE

### Il Problema del Proxy Buffering e Limiti HTTP/1.1
Nginx, per impostazione predefinita, cerca di "bufferizzare" le risposte dal backend per ottimizzare l'invio al client, distruggendo la natura "Real-Time" dell'applicativo trattenendo i pacchetti.
Inoltre, i browser su protocollo HTTP/1.1 limitano a **6** le connessioni persistenti concorrenti (tab aperti) verso lo stesso dominio.

### Mitigazione Adottata nel Piano
- L'inserimento dell'header `X-Accel-Buffering: no` all'interno dell'endpoint FastAPI ordina a Nginx di disabilitare esplicitamente il buffering per quella specifica rotta.
- Ogni 30 secondi di inattività (nessun nuovo articolo elaborato), FastAPI emette un commento vuoto SSE (`yield ": ping\n\n"`) che il client Javascript ignora. Questo garantisce traffico sul socket TCP, impedendo la chiusura per inattività imposta dai firewall/load balancer.
- Riguardo i limiti HTTP/1.1, per una web-app dashboard a schermata singola l'apertura di più di 6 schede è rara, rendendo l'uso nativo EventSource pienamente sostenibile.

---

## Conclusioni dell'Analisi

L'analisi conferma che il **Piano Implementativo della Fase B è estremamente solido e sicuro**. Impedisce categoricamente attacchi esterni tramite verifica HMAC, non richiede dipendenze aggiuntive nel backend, e neutralizza tutti i comportamenti avversi di default di driver DB, Reverse Proxy e logiche Frontend ottimistiche.
