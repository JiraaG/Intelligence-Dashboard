# Testing rules (Radar)

Path-scoped: backend pytest + frontend Jasmine/Karma specs.

## OBBLIGATORIO

1. Backend default: `python -m pytest -m "not live" -q` da `radar/` con `PYTHONPATH=backend` (o equivalente documentato in CLAUDE).
2. Non abilitare marker `live` / chiamate provider reali senza gate esplicito dell’utente.
3. Frontend: TestBed con `MOCK_MODE` esplicito quando si testano servizi articolo/mappa; **no** fallback silenzioso a mock su errore.
4. Sidebar freeze: i test **non** devono modificare o “migliorare” `radar/frontend/src/app/components/radar-sidebar/**`.
5. Leaflet nei test: usare stub `src/app/testing/leaflet.stub.ts` / pattern esistenti — non importare `leaflet.markercluster` nei componenti sotto test.

## VIETATO

- Aggiungere `TODO` / `pass` / test vuoti che mascherano fallimenti
- Hardcodare secret/API key nei test
- Riaprire vincoli prodotto (cluster radius legacy, `article-list`, ingest in `main.py`) “solo per il test”

## Criteri di accettazione

- Suite `not live` verde in locale/CI
- Spec FE non toccano path sidebar freeze
- Nuovi test coprono il comportamento aggiunto, non solo smoke vuoti
