# Plan prompt — ECC Radar: manuale operativo + expansion selettiva

> **Stato: ACTIVE (non eseguito)** — resta in `prompts/active/` finché non si produce un piano deliverable.  
> **Uso:** apri una chat in **Plan mode**, incolla il blocco sotto (da `## PROMPT` in poi).  
> **SoT già presenti:** `docs/04_ecc_framework.md`, `ecc_deep_dive_analysis_v2.md`, `.agents/AGENTS.md`, `radar/.ecc/CLAUDE.md`, handoff `plan-audit/archive/ecc/handoff_ecc_expansion.md`.  
> **Upstream:** https://github.com/affaan-m/ECC (= `everything-claude-code` / `affaan-m/ecc`).  
> **CodeWiki** https://codewiki.google/github.com/affaan-m/ecc — spesso shell vuota; **non** usarla come SoT. Preferire README + `docs/architecture/cross-harness.md` + Mintlify.

---

## PROMPT (incolla in Plan mode)

```text
Ruolo: architect ECC overlay per il monorepo Radar Informativo Globale.

Obiettivo
Produrri un PIANO ESEGUIBILE (non codice ancora) per:
1) Ampliare/aggiornare il MANUALE ECC operativo (quando usare skill/hooks/rules/agents/commands; prompt base vs skill; come espandere).
2) Estendere l’overlay Radar in modo SELETTIVO, skills-first, allineato all’architettura ECC upstream (DRY adapter, AGENTS.md Magna Carta, hooks hard-enforcement) SENZA clonare il catalogo upstream (~67 agents / ~200+ skills).

Contesto obbligatorio da leggere prima di pianificare
- docs/04_ecc_framework.md
- ecc_deep_dive_analysis_v2.md (§0–2, §5–6 se presenti)
- .agents/AGENTS.md
- radar/.ecc/CLAUDE.md (skill map)
- .cursor/hooks.json + adapters in .cursor/hooks/
- radar/.ecc/hooks/*.py + radar/.ecc/rules/*
- Lista skill SoT: .agents/skills/*/SKILL.md (+ mirror radar/.ecc/skills/)
- Upstream filosofia: skills-first; adapters sottili; comportamento durevole in skills/rules/hooks
- Vincoli prodotto NON negoziabili: sidebar freeze radar-sidebar/**; ingest solo worker.py; main.py API-only; MOCK_MODE esplicito; cluster maxClusterRadius 40 / spiderfyOnMaxZoom false; Pydantic CSV str; reti radar-edge/radar-data

Fonti upstream (fetch se serve; non installare raw)
- https://github.com/affaan-m/ECC
- https://raw.githubusercontent.com/affaan-m/ECC/main/docs/architecture/cross-harness.md
- https://raw.githubusercontent.com/affaan-m/ECC/main/hooks/README.md
- https://affaan-m-everything-claude-code.mintlify.app/concepts/overview
- NON basarti su CodeWiki se vuota

Regola d’oro (piano e deliverable devono rispettarla)
- SoT playbook = .agents/skills/<name>/SKILL.md
- Mirror flat = radar/.ecc/skills/<name>.md (sync dopo edit SoT)
- Rules SoT = radar/.ecc/rules/* ; Cursor = .cursor/rules/*.mdc (pointer/globs, no testo lungo duplicato)
- Hook logica = radar/.ecc/hooks/* ; Cursor = .cursor/hooks.json + *-adapter.py sottili
- Commands = .cursor/commands/* solo shortcut; non sostituiscono skill
- Agents = radar/.ecc/agents/* = profili Task/prompt; non auto-dispatch di massa

Cosa decidere nel piano (obbligatorio)
A. Prompt base / pre-richiesta
   - Serve uno slash/command o blocco “session preamble” sempre-on? Se sì, cosa contiene vs cosa resta in AGENTS.md.
   - Quando basta AGENTS.md+rules; quando aggiungere una riga “usa skill X”.
B. Quando creare una NUOVA skill (criteri gate)
   - Solo se: workflow ripetuto ≥2–3 volte, conoscenza non ovvia dal codice, anti-pattern costosi, path chiari when_to_use.
   - Non creare skill per: one-shot, copia di AGENTS, tutorial generici Angular/Python già coperti.
C. Quando creare/estendere un HOOK
   - Solo enforcement HARD (secret, path vietati, linter fail-closed, allowlist dominio).
   - Non usare hook per “ricordare all’agente di leggere una skill”.
D. Quando creare RULE vs SKILL vs AGENT
   - Rule = immutabile path-scoped (non violare).
   - Skill = come fare (playbook).
   - Agent = specialista Task con scope tools ristretto.
E. Gap Radar candidati (valuta priorità P0/P1/P2; proponi SOLO se chiudono gap reali)
   Esempi da valutare, non assumere necessari: ops-backup-windows, requeue-ops, complexity-routing-v2.2, nation-fetch-errors T-P1-04, overlay gemini-simple documentato.
F. Manuale
   - Dove scrivere: preferisci estendere docs/04_ecc_framework.md + puntatore da README; aggiorna ecc_deep_dive solo se stale critico.
   - Sezioni richieste: modello mentale 3 superfici; tabella “strumento → quando”; checklist nuova skill; checklist nuovo hook; anti-pattern; sync mirror.

Vincoli di esecuzione del piano
- Nessun clone/install massivo ECC nel monorepo
- Nessun tocco a radar/frontend/.../radar-sidebar/**
- Nessun commit/push senza richiesta utente
- Non inventare wiring già DONE (hooks/rules Cursor già presenti) — verifica file e proponi solo delta
- Deliverable piano: tabella task ID, file target, gate di accettazione, ordine, rischi

Output del Plan (formato)
1. Verdetto AS-IS (cosa è già wired vs documentale)
2. Matrice: Skill | Rule | Hook | Agent | Command — quando usare
3. Decisione “prompt base sempre-on” (sì/no + bozza testo se sì)
4. Lista gap P0/P1/P2 con giustificazione
5. Sequenza implementazione (manuale prima o wiring prima — scegli e motiva)
6. Gate di accettazione misurabili
7. Fuori scope esplicito

Dopo che l’utente approva il piano: solo allora passare ad Agent mode per implementare.
```

---

## Note operative (per l’operatore)

| Azione | Comando mentale |
|--------|-----------------|
| Solo capire ECC | Chat Ask + `docs/04` + deep-dive V2 |
| Progettare expansion | **Plan mode** + questo prompt |
| Implementare | Agent mode dopo approve del piano |
| Nuova skill one-shot | Skill `create-skill` Cursor + mirror `.ecc` + riga in skill map CLAUDE |
