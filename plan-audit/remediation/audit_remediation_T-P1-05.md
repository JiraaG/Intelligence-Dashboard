# Audit Report — Ticket T-P1-05: Nginx Frontend non-root (unprivileged)

> **Stato ticket:** **DONE** (verificato nel workspace principale 2026-07-16)  
> **SoT stato:** `plan_docs_audit_ticket_status.md` §3 / §16  
> **Playbook:** `plan_docs_audit_playbook.md` §3.7 / §4.7

---

## 0. Verdetto verifica workspace (post remediation)

| Check | Esito |
|-------|--------|
| Modifiche applicate al workspace principale? | **Sì** — `frontend/Dockerfile`, `frontend/nginx.conf`, `docker-compose.yml`, `docker-compose.hardened.yml` |
| Nginx gira come utente non-root? | **Sì** — `USER nginx` (Path A) |
| Porta interna Nginx impostata a 8080? | **Sì** — `listen 8080;` in `nginx.conf` |
| Dockerfile setup (chown cache/log/run/html)? | **Sì** — `RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /var/run /usr/share/nginx/html` |
| Mappatura porte Compose corretta? | **Sì** — `"80:8080"` (base) e `"127.0.0.1:80:8080"` (hardened) |
| `docker-compose.lan.yml` modificato? | **N/A / no edit** |
| `cap_add` FE rimosso? | **Sì** — drop `CHOWN`/`SETGID`/`SETUID`/`NET_BIND_SERVICE`; **tenuti** `cap_drop: ALL`, `read_only`, tmpfs |
| INF-USER-03 check | **PASS** (USER nginx Path A) |
| Script E / DoD (whoami + HC + host `/health` + healthy) | **PASS** (`nginx`, `ok`, HTTP 200, healthy) |
| Docs e regole di governance allineati? | **Sì** |

**Verdetto complessivo dopo remediation in-workspace:** **PASS** (configurazione sicura, non-root e port mapping corretti).

---

## 1. Fasi

| Fase | Stato |
|------|--------|
| FASE 3 Riproduzione | DONE (confermato che il container frontend originale eseguiva come root / porta 80) |
| FASE 4 Design + implementazione | DONE (USER nginx + listen 8080 + chown directories + Compose mapping) |
| FASE 5 Gate | DONE (Script E, Docker rebuild/config e caricamento dell'app verificati) |

---

## 2. FASE 3 — Evidenze (storico)

AS-IS pre-fix:
In precedenza, l'immagine di produzione per `radar-frontend` (basata su `nginx:alpine`) veniva eseguita con i privilegi di default dell'utente `root`, e il server Nginx ascoltava sulla porta standard `80`. Questo violava le best practice di hardening e sicurezza delle immagini di produzione, che impongono l'esecuzione di container con utenti non-root non-privilegiati per mitigare i rischi legati a potenziali exploit.

---

## 3. FASE 4 — Policy implementata

- **`frontend/Dockerfile`**:
  - `COPY --from=builder --chown=nginx:nginx … /usr/share/nginx/html`
  - `RUN chown -R nginx:nginx /var/cache/nginx /var/log/nginx /var/run /usr/share/nginx/html`
  - `USER nginx` prima di HEALTHCHECK/EXPOSE/CMD
  - HEALTHCHECK: `CMD wget -qO- http://127.0.0.1:8080/health || exit 1`
  - `EXPOSE 8080`
- **`frontend/nginx.conf`**:
  - Aggiornata la direttiva `listen` a `8080;` (porta non privilegiata).
- **`docker-compose.yml`**:
  - Port mapping `80:8080` (host plug-and-play invariato su `:80`).
  - Healthcheck `wget http://127.0.0.1:8080/health`.
  - **Rimosso** il blocco `cap_add` FE. **Pre-esistenti e conservati:** `cap_drop: ALL`, `security_opt: no-new-privileges`, `read_only`, tmpfs cache/run/tmp.
- **`docker-compose.hardened.yml`**:
  - Override porte `"127.0.0.1:80:8080"`.
- **`docker-compose.lan.yml`**:
  - **N/A / no edit** (solo Miniflux `8080:8080`; nessun mapping FE).

---

## 4. FASE 5 — Esiti (workspace principale)

```powershell
cd radar
docker compose up --build -d radar-frontend

docker compose exec radar-frontend whoami
# nginx

docker compose exec radar-frontend wget -qO- http://127.0.0.1:8080/health
# ok

curl.exe -sI http://localhost/health
# HTTP/1.1 200 OK

docker compose ps radar-frontend
# Up … (healthy)   0.0.0.0:80->8080/tcp

docker compose exec radar-frontend ps aux
# PID 1 USER nginx — nginx: master process …
```

Riverifica Cursor 2026-07-16: stessi esiti Script E / DoD (whoami=nginx, health ok, host 200, healthy, uid=101).

---

## 5. Handoff

| Item | Severità | Note |
|------|----------|------|
| **P2 backlog codice** | **OPEN** | Prossimo passo. Batch di remediation P2 (T-P2-01..T-P2-08). |

**Handoff:** Tutti i ticket di priorità P0 e P1 sono completati. **Prossimo:** Priorità P2.

---

## 6. Criteri DoD (firmati)

- [x] Utente Nginx non-root configurato via `USER nginx` (Path A).
- [x] Nginx configurato internamente sulla porta 8080.
- [x] Chown delle directory di cache, log e runtime eseguito nel Dockerfile.
- [x] Compose porta host 80 mappata a container 8080 (`80:8080`).
- [x] Hardened compose configurato su `127.0.0.1:80:8080`.
- [x] `docker-compose.lan.yml` marcato N/A.
- [x] Compose: rimosso `cap_add` FE; tenuti `cap_drop: ALL` / `read_only` / tmpfs.
- [x] Script E / DoD: whoami=`nginx`, wget `/health` ok, host HTTP 200, service healthy.
- [x] Documentazione, regole operative (`docker.md`, `AGENTS.md`, `CLAUDE.md`) e skill (`radar-docker-ops`) sincronizzate.
- [x] Stato SoT in `plan_docs_audit_ticket_status.md` impostato su DONE.
