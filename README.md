# Radar Informativo Globale

> **Intelligence Dashboard** — Un'applicazione web self-hosted e containerizzata per l'aggregazione di feed RSS e il loro arricchimento semantico via LLM. Il sistema espone localmente il frontend sulla porta `80` e l'interfaccia Miniflux sulla porta `8080`. Sebbene l'infrastruttura sia eseguita in locale tramite Docker, il funzionamento richiede l'accesso a servizi esterni: fonti RSS, Google Gemini API per il reasoning e Carto per il rendering delle tile geografiche.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Angular](https://img.shields.io/badge/Angular-21.2-DD0031?logo=angular&logoColor=white)](https://angular.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-4_services-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

---

## ⚡ Zero-Config & 100% Plug and Play
Questo progetto è stato ingegnerizzato per essere **completamente indipendente** dall'host. Grazie a un'avanzata architettura Docker Multi-Stage, l'utente finale necessita **esclusivamente di Docker** installato. Nessun requisito per Node.js, Python o database locali. Basta un solo comando (`docker compose up --build -d`) e il sistema si auto-assembla, installando le dipendenze, pre-compilando il frontend Angular e servendolo tramite Nginx.

---

## 🏗️ Architettura a Colpo d'Occhio

```mermaid
flowchart LR
    Browser([Browser]) <-->|Porta 80| Nginx[Nginx / Angular]
    Browser -->|Tile Esterni| Carto[(Carto Map)]
    
    Nginx <-->|/api/| FastAPI[FastAPI Backend]
    
    FastAPI -->|Lettura/Scrittura| PG[(PostgreSQL)]
    FastAPI -->|Scrittura| Vault[(Vault Obsidian)]
    
    FastAPI <-->|REST| Miniflux[Miniflux]
    Miniflux -->|Fetch Esterno| RSS[(Feed RSS)]
    
    FastAPI <-->|Generazione JSON| Gemini([Google Gemini API])
```

---

## 🛠️ Stack Tecnologico

| Componente | Versione / Tag | Fonte di Verità |
|---|---|---|
| **Python** | `3.12-slim` | `radar/backend/Dockerfile` |
| **Node (Build)** | `22` | `radar/frontend/Dockerfile` |
| **Angular** | `21.2` | `radar/frontend/package.json` |
| **Nginx** | `1.27-alpine` | `radar/frontend/Dockerfile` |
| **PostgreSQL** | `15` | `docker-compose.yml` |
| **Miniflux** | `2.3.2` | `docker-compose.yml` |

*Nota: Le versioni dell'ambiente Node utilizzano ora `npm ci` garantendo build immutabili bit-a-bit basate sul package-lock.*

---

## 📚 Documentazione del Progetto

La documentazione è stata suddivisa per aree tematiche. 
* 🚀 **[Guida all'Avvio (Getting Started)](docs/01_getting_started.md)** 
* ⚙️ **[Architettura e Backend](docs/02_architecture_and_backend.md)**
* 🎨 **[Frontend e UI (Interfaccia)](docs/03_frontend_and_ui.md)**
* 🧠 **[Il Framework ECC (Everything Claude Code)](docs/04_ecc_framework.md)**
* 📰 **[Fonti RSS Suggerite](RSS.txt)**: Lista dei feed testati per l'importazione.

---

## 🗂️ Struttura delle Directory

```text
Dashboard finance/                           
├── docs/                                    # Manuali architetturali e di setup
│   ├── 01_getting_started.md
│   ├── 02_architecture_and_backend.md
│   ├── 03_frontend_and_ui.md
│   └── 04_ecc_framework.md
├── RSS.txt                                  # Catalogo feed RSS consigliati
├── .agents/                                 # ECC Global Guardrails
│   ├── AGENTS.md                            # Magna Carta del progetto
│   └── skills/                              # Competenze globali
├── README.md                                # ← Questo file
│
└── radar/                                   # Repository Monorepo
    ├── backend/                             
    │   ├── app/
    │   │   ├── core/                        # Configurazione, DB, Logging
    │   │   ├── extraction/                  # Miniflux client, Parser
    │   │   ├── classification/              # Gemini client, Prompts
    │   │   └── commit/                      # DB Commit, Vault Factory
    │   └── Dockerfile
    ├── frontend/                            
    │   ├── src/app/
    │   │   ├── components/                  # RadarMap, Sidebar, Toolbar
    │   │   ├── services/                    # StateService, ArticleService
    │   │   ├── models/                      # Interfacce TypeScript
    │   │   └── shared/                      # Direttive (es. hatching)
    │   ├── angular.json                     # Configurazione build Angular
    │   └── Dockerfile
    ├── vault/                               # Dati Markdown generati (ignorato da Git)
    ├── .ecc/                                # ECC Local Workspace
    │   ├── rules/                           # Regole frontend/backend/docker
    │   ├── hooks/                           # Script pre/post esecuzione
    │   └── skills/
    └── docker-compose.yml                   # Topologia dei 4 container
```
