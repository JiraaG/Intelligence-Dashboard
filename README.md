# Radar Informativo Globale

> **Intelligence Dashboard** — A self-hosted, Docker-containerized geopolitical intelligence dashboard that aggregates RSS feeds, enriches them via Google Gemini LLM, and displays results on an interactive 2D dark map (Palantir-style).

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Angular](https://img.shields.io/badge/Angular-21.2-DD0031?logo=angular&logoColor=white)](https://angular.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-4_services-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Gemini](https://img.shields.io/badge/LLM-Gemma_4_31B-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)

---

## Vision & Purpose

**Radar Informativo Globale** transforms raw RSS news feeds into structured, geo-referenced intelligence entries. The pipeline:

1. **Ingestion** — Miniflux polls configured RSS feeds ogni 15 minuti.
2. **Enrichment** — Google Gemini LLM (Gemma 4 31B) classifica ogni articolo restituendo dati strutturati (JSON): nazione, coordinate, categoria, sentiment, pertinenza e società coinvolte.
3. **Persistence** — I dati vengono archiviati su PostgreSQL (driver puramente asincrono) e fisicamente esportati su file system in un vault compatibile con Obsidian Markdown.
4. **Visualization** — Il frontend (Angular 21) disegna una mappa interattiva a tema scuro, utilizzando tecniche avanzate di rendering visivo per mostrare allerte geografiche e raggruppare visivamente gli eventi critici (MarkerCluster).

---

## 📚 Documentazione del Progetto

Per evitare un file gigantesco, la documentazione è stata suddivisa per aree tematiche. 
Di seguito trovi i link ai file specifici, dove puoi trovare ogni dettaglio tecnico, architetturale e le guide pratiche di setup:

* 🚀 **[Guida all'Avvio (Getting Started)](docs/01_getting_started.md)** 
  * Prerequisiti, variabili `.env`, installazione via Docker Compose, gestione feed Miniflux.
* ⚙️ **[Architettura e Backend](docs/02_architecture_and_backend.md)**
  * Spiegazione della Pipeline a 3 Layer (Extraction, Classification, Commit), flussi di salvataggio, interazione DB.
* 🎨 **[Frontend e UI (Interfaccia)](docs/03_frontend_and_ui.md)**
  * Logiche Angular, Design System a 10 colori, regole per la Mappa Globale, Clustering, componenti interattivi.
* 🧠 **[Il Framework ECC (Everything Claude Code)](docs/04_ecc_framework.md)**
  * Spiegazione dell'architettura di agent orchestration alla base di questo progetto, file di configurazione (`.ecc`, `.agents`), gestione delle Rules, Hooks e come aggiungere nuove Skills all'IA.

---

## Struttura Rapida delle Directory

```
Dashboard finance/                           
├── docs/                                    # Documentazione dettagliata
│   ├── 01_getting_started.md
│   ├── 02_architecture_and_backend.md
│   ├── 03_frontend_and_ui.md
│   └── 04_ecc_framework.md
├── .agents/                                 # Competenze apprese dall'Agente IA (Skills)
├── README.md                                # ← Questo file
│
└── radar/                                   # Repository Monorepo
    ├── backend/                             # Python 3.12 (FastAPI)
    ├── frontend/                            # Angular 21 (Nginx)
    ├── vault/                               # Dati Markdown Obsidian
    ├── .ecc/                                # Regole rigide dell'architettura (Hooks/Rules)
    └── docker-compose.yml                   # Avvio unificato dell'intero stack
```

---

## Roadmap e Manutenzione

La repository viene costantemente aggiornata per migliorare l'affidabilità delle pipeline LLM (tramite prompt engineering e fallback robusti) e affinare l'estetica Palantir-like dell'interfaccia. 
Se intendi contribuire allo sviluppo tramite Intelligenza Artificiale, **ti invitiamo caldamente a leggere prima la sezione [ECC Framework](docs/04_ecc_framework.md)** per familiarizzare con le regole e i vincoli di progetto imposti nella directory `.ecc/`.

## Licenza
Distribuito sotto licenza MIT. Vedi il file `LICENSE` per ulteriori informazioni.
