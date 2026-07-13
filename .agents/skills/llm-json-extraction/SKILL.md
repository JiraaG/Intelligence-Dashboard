---
name: llm-json-extraction
description: >
  Playbook per l'integrazione con Google Gemini API tramite l'SDK ufficiale google-genai.
  Definisce il System Prompt immutabile, lo schema Pydantic per gli Structured Outputs,
  il contratto di risposta JSON e la logica di fallback geografico.
  Usare ogni volta che si modifica la logica di chiamata a Gemini in backend/app/main.py.
when_to_use:
  - Modifiche al prompt di sistema per Gemini
  - Aggiornamento dello schema Pydantic GeopoliticalArticleSchema
  - Debug di errori di parsing JSON dalla risposta Gemini
  - Aggiunta di nuovi campi al contratto di estrazione
version: 1.0.0
---

## Quando Usare Questa Skill

Carica questa skill ogni volta che:
- Modifichi `backend/app/main.py` nella sezione della chiamata Gemini
- Ricevi errori del tipo `ValidationError` da Pydantic
- Gemini restituisce un JSON incompleto o con campi non presenti nello schema
- Devi ottimizzare il System Prompt per ridurre le allucinazioni geografiche

---

## Come Funziona

### Flusso di Esecuzione

```
1. Fetch articolo da Miniflux API
2. Sanitizzazione HTML → testo pulito
3. CHECK DUPLICATO: SELECT EXISTS su articles WHERE source_url = ?
4. (se non duplicato) Costruzione messaggio Gemini
5. Chiamata google-genai con response_schema=GeopoliticalArticleSchema
6. Parsing e validazione Pydantic
7. (se OK) INSERT su PostgreSQL
8. (se FAIL) applicazione fallback + log errore
```

---

## Schema Pydantic — Contratto Immutabile

```python
from pydantic import BaseModel, Field
from typing import List, Literal

class GeopoliticalArticleSchema(BaseModel):
    """
    Contratto immutabile per l'output strutturato di Gemma.
    NON modificare i field names o i tipi senza aggiornare anche
    la tabella PostgreSQL e le query del frontend.
    """
    reasoning: str = Field(
        description="Analisi logica e considerazioni geopolitiche/industriali preliminari prima di valorizzare i campi successivi."
    )
    title: str = Field(
        description="Titolo dell'articolo normalizzato privo di elementi di clickbait. Massimo 120 caratteri."
    )
    summary: str = Field(
        description="Sintesi esecutiva densa di informazioni di massimo due frasi."
    )
    published_at: str = Field(
        description="Data di pubblicazione dell'articolo in formato ISO YYYY-MM-DD."
    )
    source_url: str = Field(
        description="URL originale dell'articolo, invariato."
    )
    country_code: str = Field(
        description="Codice ISO Alpha-2 della nazione coinvolta (es. IT, US, CN, DE, UA). Usa 'XX' se non determinabile."
    )
    latitude: float = Field(
        description="Latitudine geografica in gradi decimali. Inserisci il centroide nazionale se la città non è citata."
    )
    longitude: float = Field(
        description="Longitudine geografica in gradi decimali. Stessa regola della latitudine."
    )
    companies_involved: List[str] = Field(
        description="Elenco delle aziende o corporazioni industriali menzionate. Array vuoto [] se nessuna."
    )
    tags: List[str] = Field(
        description="Lista di tag semantici estratti. Il primo tag deve essere uguale alla primary_category."
    )
    primary_category: Literal[
        "Nucleare", "Energia", "Infrastrutture",
        "Geopolitica", "Economia", "Tecnologia",
        "Spazio", "Ambiente", "Salute", "Sicurezza"
    ] = Field(
        description="La macro-categoria principale scelta dall'elenco chiuso."
    )
    sentiment: Literal["Positivo", "Neutrale", "Negativo"] = Field(
        description="Sentiment strategico legato alla notizia."
    )
    infrastructural_entities: List[str] = Field(
        description="Elenco di asset o infrastrutture fisiche citate (es. dighe, porti, fabbriche specificate)."
    )
    relevance_level: int = Field(
        description="Grado di rilevanza geopolitica dell'articolo da 1 a 5.",
        ge=1,
        le=5
    )
```

---

## System Prompt Immutabile per Gemma 4 31B

```python
SYSTEM_PROMPT = """Sei un analista senior di intelligence geopolitica ed industriale specializzato in analisi strategica delle infrastrutture critiche ("pick-and-shovel").
Il tuo compito è estrarre dati geopolitici strutturati, ad alta densità informativa, dall'articolo di notizie fornito.

Segui tassativamente le seguenti regole operative per l'estrazione:

1. RAGIONAMENTO PRELIMINARE (Chain-of-Thought):
   Compila prima di tutto il campo 'reasoning' analizzando in modo logico ed esplicito:
   - Chi sono i veri protagonisti statali o industriali.
   - Quale risorsa critica, impianto, fab, giacimento o infrastruttura è coinvolta.
   - Come determinare le coordinate centroidi se la località non è specificata (es. centroide della nazione).
   - Quale categoria geopolitica è quella dominante.
   Questo campo serve a te per elaborare i fatti prima di estrarre le restanti chiavi.

2. CATEGORIZZAZIONE GEOPOLITICA:
   Assegna l'articolo ad ESATTAMENTE UNA delle seguenti categorie primarie (il primo tag in 'tags' deve essere identico alla categoria scelta):
   - 'Nucleare': impianti atomici, reattori, uranio arricchito, sanzioni nucleari, monitoraggio IAEA.
   - 'Energia': oleodotti, gasdotti, reti di trasmissione elettrica, transizione energetica, idrogeno, materie prime energetiche.
   - 'Infrastrutture': porti marittimi commerciali, ferrovie di collegamento merci, aeroporti cargo, corridoi commerciali fisici.
   - 'Geopolitica': elezioni, conflitti, tensioni diplomatiche, sanzioni, alleanze internazionali.
   - 'Economia': mercati finanziari, tassi di interesse, inflazione, accordi commerciali, debito.
   - 'Tecnologia': semiconduttori, intelligenza artificiale, telecomunicazioni, ricerca avanzata, biotecnologie.
   - 'Spazio': esplorazione spaziale, satelliti, lanci orbitali, missioni.
   - 'Ambiente': cambiamenti climatici, disastri naturali, inquinamento, politiche green.
   - 'Salute': pandemie, regolamentazioni sanitarie, organizzazione mondiale della sanità, farmaci strategici.
   - 'Sicurezza': cybersecurity, difesa militare, intelligence, attacchi hacker, spionaggio.

3. REQUISITI GEOGRAFICI:
   - country_code: codice ISO Alpha-2 (2 lettere maiuscole) del paese protagonista della notizia (usa 'XX' se non identificabile).
   - coordinate (latitude, longitude): determina le coordinate decimali dell'evento.
     REGOLA CRITICA: se l'articolo parla di una nazione in generale o non menziona una città precisa, usa tassativamente il CENTROIDE GEOGRAFICO di quella nazione (es. IT -> lat 41.87, lon 12.57; US -> lat 37.09, lon -95.71; UA -> lat 48.38, lon 31.17).

4. SINTESI E RIGORE:
   - title: normalizzato, rimuovi elementi di clickbait e sensazionalismo. Max 120 caratteri.
   - summary: sintesi esecutiva densa di informazioni di MASSIMO DUE FRASI complete. Inizia direttamente col soggetto.
   - sentiment: stabilisci il sentiment geopolitico strategico legato alla notizia ('Positivo', 'Neutrale', 'Negativo').
   - relevance_level: un intero da 1 (rilevanza locale/marginale) a 5 (rilevanza geopolitica globale o critica).
"""
```

---

## Implementazione Completa della Chiamata LLM

```python
import asyncio
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

async def extract_geopolitical_data(
    client: genai.Client,
    article_title: str,
    article_content: str,
    article_url: str,
    article_date: str
) -> GeopoliticalArticleSchema | None:
    """
    Chiama Gemma API con schema strutturato e ritorna il dato validato da Pydantic.
    Ritorna None in caso di errore irrecuperabile.
    """
    user_message = f"""Analizza questo articolo di notizie ed estrai le informazioni geopolitiche strategiche richieste.

TITOLO: {article_title}
URL: {article_url}
DATA DI PUBBLICAZIONE: {article_date}
CONTENUTO DELL'ARTICOLO:
{article_content[:4000]}  # Tronca a 4000 caratteri per rispettare il budget di token
"""

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemma-4-31b-it",
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=GeopoliticalArticleSchema,
                temperature=0.1,   # Bassa temperatura per output deterministico
                max_output_tokens=2048
            )
        )

        # Parsing e validazione Pydantic automatica tramite SDK
        extracted = GeopoliticalArticleSchema.model_validate_json(response.text)
        logger.info(f"Estrazione OK: {extracted.title[:60]} [{extracted.country_code}] ({extracted.primary_category})")
        return extracted

    except Exception as e:
        logger.error(f"Errore estrazione Gemma per URL {article_url}: {e}")
        # Fallback: ritorna None, il chiamante applicherà i valori di sicurezza
        return None


# FALLBACK GEOGRAFICO — Coordinate sicure quando Gemini fallisce
FALLBACK_COORDINATES = {
    "latitude": 0.0,    # Equatore, Oceano Indiano (zona sicura neutra)
    "longitude": 0.0,
    "country_code": "XX",
    "primary_category": "Infrastrutture"  # Categoria più generica come default
}

async def process_article_with_fallback(
    client: genai.Client,
    conn,
    article: dict
) -> bool:
    """
    Processa un singolo articolo con gestione completa degli errori.
    Ritorna True se inserito con successo, False altrimenti.
    """
    source_url = article.get('url', '')
    title = article.get('title', 'N/A')
    content = strip_html_tags(article.get('content', ''))
    published_at = article.get('published_at', '').split('T')[0]

    # LEVEL 2: Catch per singolo articolo
    try:
        # Step 1: Deduplicazione
        if await is_article_duplicate(conn, source_url):
            logger.debug(f"Duplicato ignorato: {source_url}")
            return False

        # Step 2: Estrazione Gemini
        extracted = await extract_geopolitical_data(
            client, title, content, source_url, published_at
        )

        # Step 3: Fallback se Gemini ha fallito
        if extracted is None:
            logger.warning(f"Applicazione fallback per: {title[:60]}")
            await insert_article_fallback(conn, title, source_url, published_at)
            return True

        # Step 4: Inserimento DB
        await insert_article(conn, extracted)
        return True

    except Exception as e:
        logger.error(f"Errore critico su articolo '{title[:60]}': {e}", exc_info=True)
        return False
```

---

## Centroidi Geografici di Riferimento

| Paese | ISO  | Lat     | Lon      |
|-------|------|---------|----------|
| Italia | IT  | 41.87   | 12.57    |
| Germania | DE | 51.17  | 10.45    |
| Francia | FR | 46.23   | 2.21     |
| USA   | US   | 37.09   | -95.71   |
| Cina  | CN   | 35.86   | 104.19   |
| Russia | RU  | 61.52   | 105.31   |
| Ucraina | UA | 48.38   | 31.17    |
| Azerbaigian | AZ | 40.14 | 47.58  |
| Giappone | JP | 36.20  | 138.25   |
| India | IN   | 20.59   | 78.96    |
| Brasile | BR | -14.24  | -51.93   |
| Arabia Saudita | SA | 23.89 | 45.08 |

---

## Esempi di Output Corretti

### Notizia su Chip in Germania:
```json
{
  "title": "TSMC inaugura la prima fab europea in Sassonia da 10 miliardi",
  "summary": "TSMC ha inaugurato a Dresda il primo impianto produttivo europeo per chip a 28nm. La Germania consolida la sua posizione come hub semiconductore del continente.",
  "published_at": "2026-06-23",
  "source_url": "https://example.com/news/tsmc-dresden",
  "country_code": "DE",
  "latitude": 51.1657,
  "longitude": 10.4515,
  "companies_involved": ["TSMC", "Infineon", "Bosch"],
  "tags": ["Chip", "Semiconduttori", "Germania", "Fab", "TSMC"],
  "primary_category": "Chip"
}
```

### Notizia Nucleare (paese generico, centroide):
```json
{
  "title": "L'Iran accelera l'arricchimento dell'uranio al 60%",
  "summary": "L'IAEA conferma che l'Iran ha aumentato la capacità di arricchimento dell'uranio. Le trattative diplomatiche sono al punto critico.",
  "published_at": "2026-06-23",
  "source_url": "https://example.com/news/iran-nuclear",
  "country_code": "IR",
  "latitude": 32.43,
  "longitude": 53.69,
  "companies_involved": ["IAEA"],
  "tags": ["Nucleare", "Iran", "IAEA", "Arricchimento", "Geopolitica"],
  "primary_category": "Nucleare"
}
```
