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

## Table of Contents

1. [Vision & Purpose](#vision--purpose)
2. [Project Structure](#project-structure)
3. [Architecture Overview](#architecture-overview)
4. [Technology Stack](#technology-stack)
5. [Backend — Deep Dive](#backend--deep-dive)
6. [Frontend — Deep Dive](#frontend--deep-dive)
7. [Database Schema](#database-schema)
8. [Docker Infrastructure](#docker-infrastructure)
9. [ECC Framework (Everything Claude Code)](#ecc-framework-everything-claude-code)
10. [Getting Started](#getting-started)
11. [API Reference](#api-reference)
12. [Development Workflow](#development-workflow)
13. [Roadmap](#roadmap)
14. [License](#license)

---

## Vision & Purpose

**Radar Informativo Globale** transforms raw RSS news feeds into structured, geo-referenced intelligence entries. The pipeline:

1. **Ingestion** — Miniflux polls configured RSS feeds every 15 minutes
2. **Enrichment** — Google Gemini LLM (Gemma 4 31B) classifies each article with structured outputs: country, coordinates, category, sentiment, relevance, companies, tags, and infrastructural entities via Chain-of-Thought reasoning
3. **Persistence** — Articles land in PostgreSQL (15, Alpine) and a Markdown+frontmatter Obsidian vault on the filesystem
4. **Visualization** — Angular 21 renders a dark-themed interactive map with country-level SVG hatching (zoom-out) and emoji markers (zoom-in), featuring split-screen sidebar with PrimeNG carousel

### Use Cases

- **Geopolitical analysts** monitoring global infrastructure threats
- **Supply chain managers** tracking semiconductor, energy, and water risks
- **OSINT researchers** correlating news across countries and categories
- **Policy makers** assessing sentiment and relevance across regions

### Key Metrics

| Metric | Detail |
|--------|--------|
| Polling interval | 15 minutes (configurable `MINIFLUX_LIMIT`) |
| LLM model | `gemma-4-31b-it` (Google Gemini) |
| Rate limiting | 4 seconds between LLM calls |
| Articles per cycle | Up to 50 (production), 2–5 (development) |
| Docker services | 4 (DB, Backend, Frontend, Miniflux) |
| Map zoom threshold | Zoom ≥ 5 = markers, Zoom < 5 = country hatching |
| GeoJSON size | 14.6 MB (local, one-shot parse on first zoom-in) |
| Clustering radius | 40 px (fixed) |

---

## Project Structure

```
Dashboard finance/                           # ← Git repository root
├── .gitignore                               # Excludes ECC-GitHub, .env, node_modules, dist, etc.
├── .agents/                                 # ECC skills directory
│   └── skills/
│       ├── angular-developer/
│       │   └── SKILL.md                     # Angular code generation skill
│       ├── llm-json-extraction/
│       │   └── SKILL.md                     # Gemini API integration playbook
│       └── spatial-data-mocking/
│           └── SKILL.md                     # Offline frontend testing playbook
├── .cursor/                                 # Cursor IDE config (empty, reserved)
├── plan.md                                  # PRD — Product Requirements Document
├── plan_backend_ecc.md                      # Backend implementation plan (ECC architecture)
├── plan_frontend_ecc.md                     # Frontend implementation plan (12 phases)
├── ecc_deep_dive_analysis.md                # Deep-dive analysis of ECC framework patterns
├── README.md                                # ← This file
│
└── radar/                                   # ← Main application monorepo
    ├── .env.example                         # Environment variables template
    ├── .gitignore                           # radar-specific ignores
    ├── docker-compose.yml                   # 4-service orchestration
    │
    ├── .ecc/                                # ECC governance layer
    │   ├── CLAUDE.md                        # Project identity + fundamental rules
    │   ├── settings.json                    # Tool allowlist, secrets redaction, context budget
    │   ├── rules/
    │   │   ├── backend.md                   # 10 backend rules (path-scoped: backend/**)
    │   │   ├── frontend.md                  # 11 frontend rules (path-scoped: frontend/**)
    │   │   └── docker.md                    # 9 Docker rules (path-scoped: docker-compose.yml, Dockerfile, nginx.conf)
    │   ├── agents/
    │   │   ├── pipeline-engineer.md         # Backend pipeline agent definition
    │   │   ├── geo-data-architect.md        # Database schema + SQL agent definition
    │   │   └── angular-map-expert.md        # Frontend map component agent definition
    │   └── hooks/
    │       ├── pre-tool-use.py              # Security scan before tool execution
    │       └── post-tool-use.py             # Linting + TODO detection after tool execution
    │
    ├── backend/                             # Python 3.12 FastAPI backend
    │   ├── Dockerfile                       # Multi-stage: builder → production (slim)
    │   ├── .dockerignore
    │   ├── app/
    │   │   ├── __init__.py
    │   │   ├── main.py                      # FastAPI app, Lifespan, pipeline loop, REST endpoints
    │   │   ├── requirements.txt             # Python dependencies (>= floor constraints)
    │   │   ├── core/
    │   │   │   ├── __init__.py
    │   │   │   ├── config.py                # Env var loading, fail-fast
    │   │   │   ├── database.py              # asyncpg pool init + DDL bootstrap
    │   │   │   └── logging.py               # Structured logging + RotatingFileHandler
    │   │   ├── extraction/                  # Layer E: Miniflux RSS extraction
    │   │   │   ├── __init__.py
    │   │   │   ├── client.py                # httpx async Miniflux API client
    │   │   │   ├── parser.py                # HTML tag stripping / sanitization
    │   │   │   └── state.py                 # Deduplication via SELECT EXISTS
    │   │   ├── classification/              # Layer C: Gemini LLM classification
    │   │   │   ├── __init__.py
    │   │   │   ├── client.py                # google-genai SDK wrapper
    │   │   │   ├── prompts.py               # Chain-of-Thought system prompt
    │   │   │   └── validator.py             # Pydantic v2 schema + fallback logic
    │   │   ├── commit/                      # Layer C (Commit): PostgreSQL + Vault
    │   │   │   ├── __init__.py
    │   │   │   ├── db_commit.py             # Upsert articles, companies, tags, junctions
    │   │   │   ├── factory.py               # Markdown + YAML frontmatter generator
    │   │   │   ├── router.py                # Vault directory bootstrap + slugified paths
    │   │   │   └── lock.py                  # filelock-based concurrency control
    │   │   └── tests/                       # pytest + pytest-asyncio test suite
    │   │       ├── __init__.py
    │   │       ├── conftest.py              # Shared fixtures
    │   │       ├── test_extraction.py
    │   │       ├── test_classification.py
    │   │       ├── test_commit.py
    │   │       ├── test_database.py
    │   │       ├── test_pipeline_smoke.py
    │   │       └── test_integration_live.py
    │   └── scripts/
    │       └── test_production_pipeline.py  # Diagnostic script for live pipeline testing
    │
    ├── frontend/                            # Angular 21 standalone frontend
    │   ├── Dockerfile                       # Multi-stage: Node 22 build → Nginx Alpine serve
    │   ├── .dockerignore
    │   ├── .editorconfig
    │   ├── .prettierrc
    │   ├── angular.json                     # ESBuild builder, global Leaflet scripts
    │   ├── package.json                     # Angular 21, PrimeNG 17, Leaflet 1.9, rxjs
    │   ├── proxy.conf.json                  # Dev proxy to backend
    │   ├── tsconfig.json
    │   ├── tsconfig.app.json
    │   ├── tsconfig.spec.json
    │   ├── nginx.conf                       # SPA routing, API proxy, gzip, security headers
    │   ├── public/
    │   │   └── favicon.ico
    │   └── src/
    │       ├── index.html                   # SEO meta, Leaflet CSS CDN fallback
    │       ├── main.ts                      # Bootstrap with app.config
    │       ├── styles.scss                  # Palantir Design System, CSS vars, Leaflet overrides
    │       └── app/
    │           ├── app.config.ts            # Providers: provideHttpClient, provideAnimations
    │           ├── app.ts                   # Shell orchestrator, 6 output handlers, Signals
    │           ├── app.html                 # Split-screen layout (70/30)
    │           ├── app.scss                 # Split-screen CSS, glassmorphism
    │           ├── app.spec.ts              # Component test
    │           ├── models/
    │           │   └── article.model.ts     # Article, CountrySummary, ArticleFilters, PrimaryCategory
    │           ├── services/
    │           │   ├── article-mock.service.ts  # 9 offline mock articles
    │           │   ├── article.service.ts       # HTTP service with auto-fallback to mock
    │           │   └── state.service.ts         # rxResource central store with computed filters
    │           ├── components/
    │           │   ├── radar-map/
    │           │   │   ├── radar-map.component.ts    # Leaflet map, dual-layer tiles, GeoJSON, markers
    │           │   │   ├── radar-map.component.html  # Map container with CSS class bindings
    │           │   │   └── radar-map.component.scss  # Zero HEX, only CSS custom properties
    │           │   ├── radar-toolbar/
    │           │   │   ├── radar-toolbar.component.ts    # Date picker, sentiment/category filters
    │           │   │   ├── radar-toolbar.component.html  # Glassmorphism floating toolbar
    │           │   │   └── radar-toolbar.component.scss  # Glassmorphism CSS, backdrop-filter
    │           │   └── radar-sidebar/
    │           │       ├── radar-sidebar.component.ts    # Single/cluster modes, p-carousel
    │           │       ├── radar-sidebar.component.html  # Article cards, sentiment badges, entities
    │           │       └── radar-sidebar.component.scss  # Sidebar glassmorphism, transitions
    │           └── shared/
    │               └── directives/
    │                   └── leaflet-hatch.directive.ts    # SVG pattern injection via MutationObserver
    │
    ├── vault/                               # Obsidian-compatible Markdown vault
    │   ├── Nucleare/
    │   ├── Elettronica/
    │   ├── Chip/
    │   ├── Acqua/
    │   ├── Energia/
    │   └── Infrastrutture/
    │       └── {COUNTRY_CODE}/
    │           └── {YYYY-MM-DD}_{slugified-title}_{hash}.md
    │
    └── data/
        └── postgres/                        # Persistent PostgreSQL data volume (bind mount)
```

---

## Architecture Overview

```
┌─────────────┐     RSS Polling      ┌──────────────┐
│  RSS Feeds  │ ──────────────────→  │   Miniflux   │
│  (Internet) │                      │  :8080       │
└─────────────┘                      └──────┬───────┘
                                            │
                                   fetch_unread()
                                            │
                                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI :8000)                     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              PIPELINE LOOP (every 900s)              │   │
│  │                                                      │   │
│  │  Layer E ──── Layer C (Classify) ──── Layer C (Commit)│   │
│  │  Extraction     ┌──────────────┐     ┌────────────┐  │   │
│  │  ┌──────────┐   │ Google Gemini│     │ PostgreSQL │  │   │
│  │  │ Miniflux │   │ Gemma 4 31B │     │ radar-db   │  │   │
│  │  │ Client   │──→│ Structured  │──→  │ :5432      │  │   │
│  │  └──────────┘   │ Output JSON │     └────────────┘  │   │
│  │       │         └──────────────┘            │        │   │
│  │       │                                     │        │   │
│  │  ┌────┴──────┐                    ┌─────────┴──────┐ │   │
│  │  │ HTML      │                    │ Markdown Vault │ │   │
│  │  │ Sanitizer │                    │ (Obsidian)     │ │   │
│  │  └───────────┘                    └────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  REST API: GET /api/articles, GET /api/countries, /health    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                    Nginx Proxy (/api/)
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                FRONTEND (Nginx + Angular :80)                 │
│                                                              │
│  ┌─────────────────────┐    ┌────────────────────────────┐  │
│  │  StateService       │    │  Component Tree            │  │
│  │  (rxResource)       │    │                            │  │
│  │                     │    │  App (Shell)               │  │
│  │  articles() ────────┼───→│  ├── RadarMapComponent     │  │
│  │  countries()        │    │  ├── RadarToolbarComponent │  │
│  │  filters()          │    │  └── RadarSidebarComponent │  │
│  └─────────────────────┘    └────────────────────────────┘  │
│                                                              │
│  Split-Screen 70/30  │  Leaflet + MarkerCluster  │  PrimeNG  │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Miniflux** polls external RSS feeds → stores entries in its own PostgreSQL tables
2. **Backend daemon** (`run_pipeline_loop`, every 900s) fetches unread entries from Miniflux API
3. For each entry: **deduplication** (`SELECT EXISTS` on `source_url`) → **HTML sanitization** → **Gemini classification** (CoT + Structured Output) → **PostgreSQL commit** (articles + companies + tags + junctions) → **Markdown vault write** (with filelock)
4. **Frontend** polls `GET /api/articles?date=YYYY-MM-DD` via `rxResource` → renders on Leaflet map

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.12 (Docker `slim`) | Runtime |
| **FastAPI** | ≥0.115 | REST API framework + Lifespan |
| **Uvicorn** | ≥0.32 | ASGI server |
| **asyncpg** | ≥0.31 | PostgreSQL async driver (pure SQL, no ORM) |
| **google-genai** | ≥0.8 | Google Gemini SDK (official) |
| **Pydantic** | ≥2.10 | Schema validation + Structured Outputs |
| **httpx** | ≥0.27 | Async HTTP client (Miniflux API) |
| **python-dotenv** | ≥1.0.1 | Environment variable loading |
| **filelock** | ≥3.12 | Cross-platform file locking for vault writes |
| **pytest** | ≥8.0 | Testing framework |
| **pytest-asyncio** | ≥0.23 | Async test support |

> **Critical**: All Python dependencies use `>=` (floor) constraints — never `==` (pin) — for Python 3.14/Windows forward compatibility.

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Angular** | 21.2 | UI framework (standalone components) |
| **TypeScript** | 5.9 | Language |
| **PrimeNG** | 17.18 | UI component library (sidebar, carousel, calendar, dropdown, chip, progressBar) |
| **PrimeIcons** | 7.0 | Icon library |
| **Leaflet** | 1.9.4 | Interactive map library |
| **Leaflet.MarkerCluster** | 1.5.3 | Spatial clustering plugin |
| **RxJS** | 7.8 | Reactive extensions |
| **Vitest** | 4.0 | Unit testing |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| **PostgreSQL** | 15 (Alpine) | Primary database |
| **Miniflux** | latest | RSS feed aggregator |
| **Nginx** | Alpine | Frontend web server + API reverse proxy |
| **Docker Compose** | v3 | Container orchestration |
| **Node.js** | 22 (Docker build) | Angular build stage |

---

## Backend — Deep Dive

### Entrypoint: `app/main.py`

The FastAPI application uses the **Lifespan** pattern for clean startup/shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    state.db_pool = await init_pool(DATABASE_URL)
    await bootstrap_database(state.db_pool)
    initialize_vault_directories(OBSIDIAN_VAULT_PATH)
    state.miniflux_client = MinifluxClient(...)
    state.classification_client = ClassificationClient()
    state.pipeline_task = asyncio.create_task(run_pipeline_loop(state))
    yield
    # Shutdown
    state.pipeline_task.cancel()
    await state.db_pool.close()
```

### Pipeline Architecture (3 Layers)

#### Layer E: Extraction

| Module | File | Responsibility |
|--------|------|----------------|
| **MinifluxClient** | [`extraction/client.py`](radar/backend/app/extraction/client.py) | Fetches unread entries via httpx, marks entries as read |
| **HTML Parser** | [`extraction/parser.py`](radar/backend/app/extraction/parser.py) | Strips HTML tags, normalizes whitespace, truncates for LLM context |
| **State Manager** | [`extraction/state.py`](radar/backend/app/extraction/state.py) | Pre-Gemini deduplication via `SELECT EXISTS` on `source_url` |

#### Layer C: Classification

| Module | File | Responsibility |
|--------|------|----------------|
| **Gemini Client** | [`classification/client.py`](radar/backend/app/classification/client.py) | Wraps `google-genai` SDK, configures Structured Output |
| **Prompt Engine** | [`classification/prompts.py`](radar/backend/app/classification/prompts.py) | Chain-of-Thought system prompt with 6-category classification |
| **Validator** | [`classification/validator.py`](radar/backend/app/classification/validator.py) | Pydantic v2 `GeopoliticalArticleSchema`, country code normalization, fallback logic |

#### Layer C: Commit

| Module | File | Responsibility |
|--------|------|----------------|
| **DB Commit** | [`commit/db_commit.py`](radar/backend/app/commit/db_commit.py) | Upsert articles (INSERT ON CONFLICT), companies, tags, junction tables |
| **Markdown Factory** | [`commit/factory.py`](radar/backend/app/commit/factory.py) | Generates Markdown body + YAML frontmatter for Obsidian |
| **Vault Router** | [`commit/router.py`](radar/backend/app/commit/router.py) | Creates vault directories (`{category}/{COUNTRY}/`), generates slugified filenames |
| **File Lock** | [`commit/lock.py`](radar/backend/app/commit/lock.py) | Cross-platform `filelock` for concurrent vault writes |

### Pydantic Schema (`GeopoliticalArticleSchema`)

```python
class GeopoliticalArticleSchema(BaseModel):
    reasoning: str                        # CoT analysis
    title: str                            # Max 120 chars, no clickbait
    summary: str                          # 1-2 sentence executive summary
    published_at: str                     # ISO YYYY-MM-DD
    source_url: str                       # Original URL
    country_code: str                     # ISO Alpha-2 ('XX' = unknown)
    latitude: float                       # Decimal degrees
    longitude: float                      # Decimal degrees
    companies_involved: List[str]         # Empty [] if none
    tags: List[str]                       # First tag = primary_category
    primary_category: Literal["Nucleare","Elettronica","Chip","Acqua","Energia","Infrastrutture"]
    sentiment: Literal["Positivo","Neutrale","Negativo"]
    infrastructural_entities: List[str]   # Physical assets (dams, ports, factories)
    relevance_level: int                  # 1–5 scale
```

### Error Handling (3-Level)

1. **Level 1 — Daemon**: `run_pipeline_loop` wraps the entire cycle in `try/except`, logs critical errors, sleeps 900s, NEVER crashes
2. **Level 2 — Cycle**: `run_pipeline_cycle` wraps the batch in `try/except`, logs cycle errors, continues
3. **Level 3 — Article**: Individual article processing wrapped in `try/except`, continues to next article on failure

### Fallback Mechanism

If Gemini API fails irrecoverably, [`get_fallback_article()`](radar/backend/app/classification/validator.py:70) produces a safe neutral article with:
- `country_code="XX"`, `latitude=0.0`, `longitude=0.0`
- `primary_category="Infrastrutture"`, `sentiment="Neutrale"`
- `relevance_level=1`, empty companies and entities

### Rate Limiting

A mandatory `asyncio.sleep(4)` between each LLM call prevents API quota exhaustion.

---

## Frontend — Deep Dive

### Architecture: Standalone Components + Signals

The frontend follows **Angular 21 standalone component architecture** with zero `NgModule` usage. All state management uses **Signals** (no `BehaviorSubject`).

### Component Tree

```
App (Shell Orchestrator)
├── RadarMapComponent     ← Leaflet map, GeoJSON, markers, clustering
├── RadarToolbarComponent ← Date picker, sentiment/category filters
└── RadarSidebarComponent ← Article cards, carousel, entities
```

### State Management: [`state.service.ts`](radar/frontend/src/app/services/state.service.ts)

```
filters (Signal) ──→ articlesResource (rxResource) ──→ articles (computed)
                                    │                       │
                                    ▼                       ▼
                              HTTP GET /api/articles    Client-side filter
                              (on date change only)     (sentiment, categories)
                                                            │
                                                            ▼
                                                    countries (computed)
                                                    (grouped by country_code)
```

- **`rxResource`** triggers HTTP fetch only when `date` changes — sentiment/category filters are applied client-side via `computed()`
- **`countries`** is derived from filtered articles, grouping by `country_code` with category sets

### Core Components

#### [`radar-map.component.ts`](radar/frontend/src/app/components/radar-map/radar-map.component.ts)

- **Dual-layer tile system**: `dark_nolabels` (z-index 0) + `dark_only_labels` on `labelsPane` (z-index 650)
- **GeoJSON loading**: One-shot parse via `requestAnimationFrame`, 14.6 MB `countries.geo.json` from local `assets/data/`
- **Zoom logic**: 
  - Zoom < 5 → SVG hatching on countries (6 category colors via patterns), markers hidden
  - Zoom ≥ 5 → Emoji markers with category icons, hatching faded
- **MarkerClusterGroup**: 40px radius, custom glassmorphism styling
- **3 output events**: `markerClicked` (single article), `clusterClicked` (article array), `countryClicked` (article array)
- **Leaflet access**: `(window as any).L` pattern (ESBuild compatibility — loaded as global scripts in `angular.json`)

#### [`leaflet-hatch.directive.ts`](radar/frontend/src/app/shared/directives/leaflet-hatch.directive.ts)

- **MutationObserver** detects when Leaflet SVG overlay renders
- Injects 6 SVG `<pattern>` definitions (one per category) into the SVG `<defs>`
- Applies patterns to `path.country-fill` elements based on country data
- Supports multi-category countries (stacked diagonal patterns)

#### [`radar-sidebar.component.ts`](radar/frontend/src/app/components/radar-sidebar/radar-sidebar.component.ts)

- **Two modes**:
  - **Single**: One article selected, full detail view
  - **Cluster**: Multiple articles, `p-carousel` with navigation
- **Article card**: Sentiment badge (color-coded), relevance stars (1–5), category chip, infrastructural entities chips, source link
- **Glassmorphism**: `backdrop-filter: blur(20px)`, `rgba(10, 10, 15, 0.95)` background

#### [`radar-toolbar.component.ts`](radar/frontend/src/app/components/radar-toolbar/radar-toolbar.component.ts)

- `p-calendar` for date selection
- `p-dropdown` (multi-select) for sentiment filter: Positivo / Neutrale / Negativo
- `p-dropdown` (multi-select) for category filter: all 6 categories
- Glassmorphism floating design, `z-index: 900`

### Design System (Palantir Theme)

All colors are defined as **CSS custom properties** in [`styles.scss`](radar/frontend/src/styles.scss) — zero hardcoded HEX in components.

| Category | CSS Variable | Color | Hex |
|----------|-------------|-------|-----|
| Nucleare | `--color-nucleare` | Orange | `#FF6B35` |
| Elettronica | `--color-elettronica` | Cyan | `#00D4FF` |
| Chip | `--color-chip` | Purple | `#7B2FBE` |
| Acqua | `--color-acqua` | Blue | `#0080FF` |
| Energia | `--color-energia` | Yellow | `#FFD700` |
| Infrastrutture | `--color-infrastrutture` | Green | `#4CAF50` |

| Sentiment | CSS Variable | Color |
|-----------|-------------|-------|
| Positivo | `--color-sentiment-pos` | `#3fb950` |
| Neutrale | `--color-sentiment-neu` | `#8b949e` |
| Negativo | `--color-sentiment-neg` | `#f85149` |

### Category Emoji Icons

| Category | Emoji |
|----------|-------|
| Nucleare | ⚛️ |
| Elettronica | 📡 |
| Chip | 💾 |
| Acqua | 💧 |
| Energia | ⚡ |
| Infrastrutture | 🏗️ |

### Leaflet + ESBuild Compatibility

Since ESBuild cannot bundle Leaflet's CSS/image assets, Leaflet is loaded as **global scripts** in [`angular.json`](radar/frontend/angular.json:40-42):

```json
"scripts": [
  "node_modules/leaflet/dist/leaflet.js",
  "node_modules/leaflet.markercluster/dist/leaflet.markercluster.js"
]
```

Components access Leaflet via `(window as any).L` — **no `import * as L from 'leaflet'`** in component files.

### Mock Service (`article-mock.service.ts`)

Provides 9 realistic mock articles from actual RSS sources for **offline frontend development** without backend. The `ArticleService` auto-falls back to mock data when the backend is unreachable.

---

## Database Schema

### Tables

```sql
-- articles: Primary entity
CREATE TABLE articles (
    id                      SERIAL PRIMARY KEY,
    title                   TEXT NOT NULL,
    summary                 TEXT NOT NULL,
    published_at            DATE NOT NULL,
    source_url              TEXT NOT NULL UNIQUE,
    country_code            CHAR(2) NOT NULL DEFAULT 'XX',
    latitude                DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    longitude               DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    primary_category        VARCHAR(50) NOT NULL CHECK (primary_category IN (
                                'Nucleare','Elettronica','Chip','Acqua','Energia','Infrastrutture')),
    sentiment               VARCHAR(20) NOT NULL CHECK (sentiment IN ('Positivo','Neutrale','Negativo')),
    relevance_level         INTEGER NOT NULL CHECK (relevance_level BETWEEN 1 AND 5),
    infrastructural_entities TEXT[] NOT NULL DEFAULT '{}',
    feed_title              TEXT NOT NULL DEFAULT 'RSS Feed',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- companies: Unique company names
CREATE TABLE companies (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- tags: Unique semantic tags
CREATE TABLE tags (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- article_companies: Many-to-many junction
CREATE TABLE article_companies (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, company_id)
);

-- article_tags: Many-to-many junction
CREATE TABLE article_tags (
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (article_id, tag_id)
);
```

### Indices

| Index | Columns | Purpose |
|-------|---------|---------|
| `idx_articles_published_at` | `published_at DESC` | Date-based queries |
| `idx_articles_geo_date` | `published_at, latitude, longitude` | Geo-temporal queries |
| `idx_articles_country_date` | `country_code, published_at DESC` | Country aggregation |
| `idx_articles_category` | `primary_category, published_at DESC` | Category filtering |

### Upsert Pattern

Companies and tags use safe upsert to avoid duplicates:

```sql
INSERT INTO companies (name) VALUES ($1)
ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
RETURNING id;
```

---

## Docker Infrastructure

### Service Overview

| Service | Image | Port | Healthcheck |
|---------|-------|------|-------------|
| **radar-db** | `postgres:15-alpine` | — (internal) | `pg_isready` |
| **radar-backend** | Custom (Python 3.12-slim) | — (internal) | `curl /health` |
| **radar-frontend** | Custom (Nginx Alpine) | `80` | `curl /health` |
| **radar-miniflux** | `miniflux/miniflux:latest` | `8080` | — |

### Network

All services communicate over a dedicated internal bridge network `radar-network`. Only `radar-frontend:80` and `radar-miniflux:8080` are exposed to the host.

### Volumes

- **PostgreSQL data**: Bind mount `./data/postgres` → `/var/lib/postgresql/data` (persistent, survives `docker-compose down -v`)
- **Obsidian vault**: Bind mount `./vault` → `/app/vault` (accessible from host for browsing/modification)

### Nginx Configuration

The [`nginx.conf`](radar/frontend/nginx.conf) provides:

- **SPA routing**: `try_files $uri $uri/ /index.html` — all non-file routes serve Angular
- **API proxy**: `/api/` → `http://radar-backend:8000/api/` — no CORS issues in production
- **Gzip compression**: Level 6 for text, JSON, SVG
- **Cache strategy**:
  - JS/CSS/fonts: 7-day immutable cache (Angular hashed filenames)
  - GeoJSON: 1-day cache
  - `index.html`: No cache (immediate updates)
- **Security headers**: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy`

### Environment Variables

All credentials are stored in `.env` (gitignored). Template provided as [`.env.example`](radar/.env.example):

| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_MODEL` | LLM model name (default: `gemma-4-31b-it`) |
| `MINIFLUX_API_URL` | Miniflux base URL |
| `MINIFLUX_API_KEY` | Miniflux API key |
| `MINIFLUX_ADMIN_USERNAME` | Miniflux admin username |
| `MINIFLUX_ADMIN_PASSWORD` | Miniflux admin password |
| `MINIFLUX_LIMIT` | Max articles per polling cycle |
| `POSTGRES_USER` | PostgreSQL user |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |
| `DATABASE_URL` | Full PostgreSQL connection string (auto-constructed) |

---

## ECC Framework (Everything Claude Code)

The project is governed by the **ECC framework** — a path-scoped rules engine, agent definitions, skills, and hooks that constrain AI-assisted development.

### Core Files

| File | Purpose |
|------|---------|
| [`CLAUDE.md`](radar/.ecc/CLAUDE.md) | Project identity, stack declaration, 4 fundamental rules, pipeline diagram, skill map |
| [`settings.json`](radar/.ecc/settings.json) | Tool allowlist/denylist, network rules, secret redaction patterns, context budget, agent profiles |

### Fundamental Rules (from `CLAUDE.md`)

1. **80/20 Context Budget**: Maximum 80% context window utilization, checkpoint at threshold
2. **No Placeholders**: Zero `TODO`, `FIXME`, `HACK`, `pass`, `NotImplementedError`
3. **Secret Separation**: Credentials only in `.env`, never hardcoded
4. **Code Completeness**: Every function fully implemented, compile-ready

### Path-Scoped Rules

| Rule File | Scope | Key Directives |
|-----------|-------|----------------|
| [`backend.md`](radar/.ecc/rules/backend.md) | `backend/**` | `>=` dependencies, daemon never stops, pre-Gemini dedup, 3-level errors, env vars, structured logging, immutable Pydantic, `main:app` entrypoint, 4s rate limit, graceful fallback |
| [`frontend.md`](radar/.ecc/rules/frontend.md) | `frontend/**` | `browser/` build output, standalone components only, Signals for state, local GeoJSON, immutable CSS palette, zoom logic (5 threshold), 70/30 split-screen, 40px clustering, no hardcoded data, `--legacy-peer-deps`, global Leaflet scripts |
| [`docker.md`](radar/.ecc/rules/docker.md) | `docker-compose.yml`, `**/Dockerfile`, `nginx.conf` | 4 immutable service names, persistent volume, internal network, healthchecks, `.env` credentials, Python 3.12-slim, local build copy, nginx.conf standards, `.dockerignore` mandatory |

### Agent Profiles

| Agent | Scope | Specialization |
|-------|-------|----------------|
| [`pipeline-engineer`](radar/.ecc/agents/pipeline-engineer.md) | `backend/`, `.py`, `.toml`, `.txt` | Async loop, Miniflux integration, Gemini calls, PostgreSQL writes |
| [`geo-data-architect`](radar/.ecc/agents/geo-data-architect.md) | `backend/app/db/`, `backend/app/models/` | SQL DDL, indices, upsert patterns, API query contracts |
| [`angular-map-expert`](radar/.ecc/agents/angular-map-expert.md) | `frontend/`, `.ts`, `.html`, `.scss`, `.css`, `.json` | Leaflet config, hatching SVG, CSS transitions, split-screen, clustering, mock service |

### Hooks

| Hook | Trigger | Action |
|------|---------|--------|
| [`pre-tool-use.py`](radar/.ecc/hooks/pre-tool-use.py) | Before tool execution | Security scan: forbidden paths, secret patterns, dangerous commands, unauthorized domains. Blocks execution (`sys.exit(1)`) on violation. |
| [`post-tool-use.py`](radar/.ecc/hooks/post-tool-use.py) | After tool execution | Linting (ruff for Python, eslint for TypeScript), TODO/FIXME/HACK detection. Non-blocking (`sys.exit(0)` always). |

### Skills (`.agents/skills/`)

| Skill | Purpose |
|-------|---------|
| **angular-developer** | Angular code generation, reactivity (signals, `linkedSignal`, `resource`), forms, DI, routing, SSR, accessibility, animations, styling, testing |
| **llm-json-extraction** | Google Gemini API integration via `google-genai` SDK — System Prompt, Pydantic schema for Structured Outputs, JSON response contract, geographic fallback logic |
| **spatial-data-mocking** | Offline frontend testing — mock dataset, mock service toggle, visual checklists for cluster, split-screen, hatching SVG, carousel |

### Pattern Extracted (from `ecc_deep_dive_analysis.md`)

1. **Path-Scoped Rules & Architectural Sandbox**: Rules automatically scope to file patterns, ensuring backend rules never conflict with frontend or Docker rules
2. **Strict Output Contract & Verification Loop**: Pydantic schema is the single source of truth; frontend `Article` interface mirrors backend `GeopoliticalArticleSchema` exactly
3. **Decoupled Service-Driven Architecture & Offline Mocking**: Frontend can run entirely without backend via `ArticleMockService`, enabling parallel development

---

## Getting Started

### Prerequisites

- **Docker** & **Docker Compose** v2+
- **Node.js** 22+ (for local frontend dev)
- **Python** 3.12+ (for local backend dev)
- Google Gemini API key ([get one here](https://aistudio.google.com/app/apikey))

### Quick Start (Full Docker Stack)

```bash
# 1. Clone the repository
git clone <your-repo-url> radar-globale
cd radar-globale/radar

# 2. Create .env from template
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/macOS

# 3. Edit .env with your credentials
#    - GEMINI_API_KEY=<your-key>
#    - MINIFLUX_API_KEY=<your-key>
#    - MINIFLUX_ADMIN_PASSWORD=<your-password>
#    - POSTGRES_PASSWORD=<your-password>

# 4. Start all services
docker compose up -d

# 5. Check service health
docker compose ps

# 6. Access the dashboard
#    → http://localhost:80
# 7. Access Miniflux admin
#    → http://localhost:8080
```

### Local Development (Frontend Only)

```bash
cd radar/frontend

# Install dependencies (--legacy-peer-deps REQUIRED)
npm install --legacy-peer-deps

# Start dev server with proxy to backend
npm run start

# → http://localhost:4200
# API calls proxied to http://localhost:8000 (see proxy.conf.json)
```

### Local Development (Backend Only)

```bash
cd radar/backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r app/requirements.txt

# Set environment variables
set DATABASE_URL=postgresql://radar_user:password@localhost:5432/radar_db
set GEMINI_API_KEY=your-key
# ... etc.

# Run development server
uvicorn app.main:app --reload --port 8000
```

### Verify Installation

```bash
# Backend health
curl http://localhost:8000/health
# → {"status":"ok","service":"radar-backend"}

# Articles API (replace date)
curl "http://localhost:8000/api/articles?date=2026-06-25"
# → [] (empty if no articles yet, or JSON array)

# Frontend health
curl http://localhost:80/health
# → ok
```

---

## API Reference

### `GET /health`

Healthcheck endpoint for Docker health monitoring.

**Response:**
```json
{ "status": "ok", "service": "radar-backend" }
```

### `GET /api/articles`

Returns geopolitically classified articles for a given date.

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `date` | string | ✅ | ISO date format `YYYY-MM-DD` |
| `sentiment` | string | ❌ | Filter: `Positivo`, `Neutrale`, `Negativo` |
| `relevance_level` | integer | ❌ | Filter: 1–5 |

**Response:**
```json
[
  {
    "id": 1,
    "title": "Analisi strategica di Micron Technology Inc",
    "summary": "Micron registra ricavi record grazie alla domanda di memorie per AI...",
    "published_at": "2026-06-25",
    "source_url": "https://example.com/article",
    "country_code": "US",
    "latitude": 37.0902,
    "longitude": -95.7129,
    "primary_category": "Chip",
    "sentiment": "Positivo",
    "relevance_level": 4,
    "companies_involved": ["Micron Technology", "NVIDIA"],
    "tags": ["Chip", "Semiconduttori", "AI"],
    "infrastructural_entities": ["Micron Fab 16", "Boise Headquarters"],
    "feed_title": "Yahoo Finance"
  }
]
```

### `GET /api/countries`

Returns country-level aggregation (article counts + categories) for map hatching.

**Parameters:** Same as `/api/articles` (date required, sentiment/relevance optional)

**Response:**
```json
[
  {
    "country_code": "US",
    "categories": ["Chip", "Energia"],
    "article_count": 15
  },
  {
    "country_code": "CN",
    "categories": ["Chip", "Acqua", "Energia"],
    "article_count": 8
  }
]
```

---

## Development Workflow

### Branch Strategy

```
main       ← Production-ready code
  └─ develop ← Active development branch (DEFAULT)
       └─ feature/*  ← Feature branches
```

### Testing

```bash
# Backend tests
cd radar/backend
pytest app/tests/ -v

# Frontend tests
cd radar/frontend
npm run test

# Production pipeline diagnostic
cd radar/backend
python scripts/test_production_pipeline.py
```

### Code Quality

- **Python**: ruff linting enforced by post-tool-use hook
- **TypeScript**: eslint linting enforced by post-tool-use hook
- **Forbidden patterns**: `TODO`, `FIXME`, `HACK`, `NotImplementedError` detected by hooks
- **Type hints**: Mandatory on all public Python functions
- **Structured logging**: `logging.getLogger("radar.*")` — no `print()` statements

### Adding RSS Feeds

1. Log into Miniflux admin (`http://localhost:8080`)
2. Navigate to **Feeds** → **Add Feed**
3. Enter the RSS feed URL and select a category
4. New entries will be picked up on the next pipeline cycle (≤15 minutes)

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Core ingestion pipeline (Miniflux → Gemini → PostgreSQL + Vault) |
| **Phase 2** | ✅ Complete | FastAPI REST API with Lifespan-managed background daemon |
| **Phase 3** | ✅ Complete | Angular 21 frontend: Leaflet map, split-screen, hatching SVG, markers, clustering |
| **Phase 4** | ✅ Complete | Docker infrastructure: 4 services, healthchecks, nginx reverse proxy |
| **Phase 5** | ✅ Complete | ECC governance: rules, agents, hooks, skills |
| **Phase 6** | 🔜 Planned | User authentication & multi-user support |
| **Phase 7** | 🔜 Planned | Advanced analytics dashboard (trends, heatmaps, time-series) |
| **Phase 8** | 🔜 Planned | Custom RSS feed management UI |
| **Phase 9** | 🔜 Planned | WebSocket real-time updates |
| **Phase 10** | 🔜 Planned | Export to PDF/CSV reports |

---

## License

MIT License — see [LICENSE](./LICENSE) file for details.

---

*Built with ❤️ using Python, Angular, PostgreSQL, Docker, and Google Gemini. Governed by the ECC (Everything Claude Code) framework.*
