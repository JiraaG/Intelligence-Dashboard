# Prompt — T-P1-05 REMEDIATION (orchestratore multi-agente)

> **Uso:** copia il blocco `text` sotto in un nuovo chat Agent (orchestratore).  
> **Scope:** solo T-P1-05 — Nginx frontend unprivileged (`USER nginx` + listen 8080) **oppure** eccezione SoT documentata.  
> **Non** commit/push salvo richiesta esplicita. **Non** toccare `radar-sidebar/**`. **Non** aprire batch P2 in questo ticket.  
> **Precondizioni:** T-P1-04 DONE (`51225b5`). Branch tipico: `refactor/testing`.

```text
/goal Implementa T-P1-05 (Nginx frontend non-root) nel workspace
`c:\Users\lucag\Documents\Dashboard finance` secondo la policy sotto.
Usa sotto-agenti (Task tool) dove utile; tu resti orchestratore: review, gate, SoT.
NON commitare / NON pushare. NON toccare radar-sidebar/**. NON aprire P2 salvo richiesta.

========================================================================
## 0. Contesto SoT
========================================================================

Ticket: **T-P1-05** · scratch **INF-AUD-02** (elevato P1 — App. F §F.2)
Sintomo: container FE gira come `root` (porta 80 privilegiata).
Path A (preferito): `USER nginx` + `listen 8080` + Compose `80:8080` + healthcheck `wget …:8080/health`.
Path B (alternativa umana): documentare eccezione SoT in `docker.md` / runbook (perché resta root) — **solo se decisione esplicita**.

SoT: `plan-audit/active/audit_problemi_documentazione_risoluzione.md` §3
Playbook: `plan-audit/active/audit_problemi_documentazione.md` §3.7 / §4.7 / Script E
Skills: `.agents/skills/radar-docker-ops`
ECC: `radar/.ecc/rules/docker.md`
Report: crea `plan-audit/remediation/audit_remediation_T-P1-05.md`
Branch: `refactor/testing`. Gate: Phase 6 / Gate Verde.

========================================================================
## 0.1 Policy (VINCOLANTE se Path A)
========================================================================

| Area | Azione |
|------|--------|
| `radar/frontend/nginx.conf` | `listen 8080;` (non 80) |
| `radar/frontend/Dockerfile` | utente non-root `nginx`; ownership su html/cache/run; niente root finale |
| `docker-compose.yml` | FE `ports: "80:8080"`; healthcheck `wget http://127.0.0.1:8080/health` |
| `docker-compose.hardened.yml` / `lan.yml` | allineare porte/health se presenti |
| Docs | `docker.md`, `radar-docker-ops`, `docs/01_getting_started.md`, runbook se porte citate |
| UI | `http://localhost/` deve continuare a funzionare (host 80 → container 8080) |
| Fuori scope | P2; FE Angular app logic; sidebar; T-P1-04 |

========================================================================
## 1. Sotto-agenti suggeriti
========================================================================

| ID | Ruolo | Touch allowlist |
|----|-------|-----------------|
| **A** | Dockerfile + nginx.conf | `radar/frontend/Dockerfile`, `nginx.conf` |
| **B** | Compose overlays | `docker-compose.yml`, `hardened.yml`, `lan.yml` |
| **C** | Docs + Script E + gate | `plan-audit/remediation/audit_remediation_T-P1-05.md`, SoT §3, `docker.md` / docker-ops; esegue Script E |

A∥B poi C.

========================================================================
## 2. Gate (DoD)
========================================================================

```powershell
cd radar
docker compose up --build -d radar-frontend
docker compose exec radar-frontend whoami
# Atteso Path A: nginx (non root)
docker compose exec radar-frontend wget -qO- http://127.0.0.1:8080/health
curl.exe -sI http://localhost/health
# UI: http://localhost/ ancora OK
```

- [ ] `whoami` → `nginx` (Path A) **oppure** eccezione SoT firmata (Path B)
- [ ] Health FE healthy; UI su :80 host
- [ ] SoT T-P1-05 DONE; handoff **P2 batch** o ticket P2 scelto
- [ ] Nessun commit/push

### Output orchestratore (italiano)
1. Verdetto PASS / PASS_WITH_GAPS / FAIL
2. Path A vs B
3. File touched + esiti Script E
4. Diff OPEN SoT
5. Handoff one-liner P2
```
