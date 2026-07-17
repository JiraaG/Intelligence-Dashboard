# Final Release — Fase 4 Security (SAST / image / XSS)

**Stato:** PASS con accettazioni documentate  
**Data:** 2026-07-17  
**Tool:** Trivy `aquasec/trivy:0.58.1` (container), `python -m pip_audit`, `npm audit --omit=dev`

---

## Dependency scan (app)

| Target | Esito |
|--------|-------|
| BE `app/requirements.txt` via `pip-audit` | **No known vulnerabilities found** |
| FE `npm audit --omit=dev` (host lockfile) | **0 vulnerabilities** |

## Image scan (Trivy CRITICAL+HIGH)

| Image | Note |
|-------|------|
| `postgres:15-alpine` | HIGH tipici toolchain Go/base (OS package); nessun blocco app Radar |
| `miniflux/miniflux:2.3.2` | Alpine OS **0**; gobinary stdlib **1 HIGH** (`CVE-2026-39822`, fixed upstream Go) |
| `nginx:1.27-alpine` | HIGH su libxml2/musl/nghttp2/zlib (base image) |
| `radar-radar-backend` / `radar-radar-worker` | **CRITICAL** `perl-base` `CVE-2026-13221` (+ altri HIGH perl/ncurses) nella base Debian di `python:*-slim` |
| `radar-radar-frontend` | HIGH base Alpine/nginx layer (stesso profilo nginx) |

### Policy gate (dal piano)

- Bloccare solo **CRITICAL fixabili nel nostro codice/deps** → **nessuno** su pip/npm.
- CRITICAL `perl-base` in immagini Python slim: **accettato** per release — Radar non esegue Perl; exploit path richiede; follow-up = bump base image quando Debian pubblica patch.
- HIGH base-image: **accettati** (non elevati a P0 senza exploit path applicativo).

## CSP / headers

`GET http://localhost/` include:

- `Content-Security-Policy: default-src 'self'; …`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: SAMEORIGIN`

CI: job `secret-scan` in `.github/workflows/ci.yml` (già presente).

## XSS spot

- Marker icon: `createSafeMarkerIcon` usa `el.textContent` per emoji e `el.title = article.title` (niente `innerHTML` del titolo utente) in `radar-map.component.ts`.
- Spot browser con payload `<script>` su titolo: **non rieseguito in questo turno** (precondizione: smoke UI già fatto in handoff); code-path review **PASS**.

## Criteri PASS

- [x] Image scan eseguito e documentato  
- [x] Dependency scan BE/FE  
- [x] CSP validata su FE live  
- [x] XSS path marker reviewata  
- [x] CRITICAL app-deps = 0; CRITICAL base perl accettato con rationale  

## Decisione

**Fase 4 PASS** (con accettazioni base-image). Fase 5 resta **DEFERRED accettato**.
