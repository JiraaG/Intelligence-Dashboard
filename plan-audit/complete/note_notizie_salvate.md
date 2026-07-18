# Feature note — Notizie Salvate (2026-07-17)

## Scope

Vault articoli salvati **cross-day**, indipendente dal date picker day-view.

## Delivered

| Layer | Change |
|-------|--------|
| DB | Migration `010_articles_is_saved.sql` — `articles.is_saved BOOLEAN NOT NULL DEFAULT FALSE` + partial index |
| API | `GET /api/saved-summary`; `GET /api/articles?saved=true` (no date); `PATCH .../saved_status` (save ⇒ `is_read=true`); `PATCH .../read_status` (unread ⇒ `is_saved=false`) |
| FE | Toolbar `NOTIZIE SALVATE` + tooltip Nazioni Salvate; `StateService` saved path; card **Salva / Rimuovi dai salvati**; click nazione = stesso path LETTE/TROVATE (`fitBounds` + `flyTo` 6 + spiderfy) |
| Docs | Product manuals 01–04, README, ops/runbook, AGENTS, ECC CLAUDE/rules/skills |

## Coupling

- unread (`is_read=false`) ⇒ `is_saved=false`
- save (`is_saved=true`) ⇒ `is_read=true`
- unsave non forza unread; auto-read non auto-salva

## Smoke verified

- Migration `010` applied on `radar-backend` startup
- PATCH saved ×25 → `saved-summary` rows + `articles?saved=true` total=25
- Unread coupling → `is_saved=false`
- UI: counter toolbar, tooltip nazioni, open country carousel + **zoom + spiderfy** + **Rimuovi dai salvati**
- Worker cycle OK

## Restore point

Commit su `develop` con messaggio `feat(radar): Notizie Salvate …` — usare questo SHA per rollback della feature.

## SoT skills

- `.agents/skills/radar-api-contract/SKILL.md` (mirror `.ecc`)
- `.agents/skills/radar-sidebar-freeze/SKILL.md` (mirror `.ecc`)
