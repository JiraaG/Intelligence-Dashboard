# validator.py — Pydantic Schema Validation & Fallback

from pydantic import BaseModel, Field, field_validator
from typing import List, Literal

class GeopoliticalArticleSchema(BaseModel):
    """
    Schema di validazione Pydantic ed estrazione strutturata dei dati.
    Mantiene la coerenza del modello dati per il salvataggio nel database relazionale
    e l'esportazione frontmatter di Obsidian.
    """
    # Strutturazione CoT per l'analisi preliminare del modello
    reasoning: str = Field(
        description="Analisi logica e considerazioni geopolitiche/industriali preliminari prima di valorizzare i campi successivi."
    )
    title: str = Field(
        description="Titolo normalizzato privo di elementi di clickbait. Massimo 120 caratteri."
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
    primary_category: Literal["Nucleare", "Elettronica", "Chip", "Acqua", "Energia", "Infrastrutture"] = Field(
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

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        """Pulisce e normalizza il codice paese a 2 lettere maiuscole."""
        if not value:
            return "XX"
        clean_val = value.strip().upper()
        if len(clean_val) != 2:
            return "XX"
        return clean_val


def get_fallback_article(title: str, source_url: str, published_at: str) -> GeopoliticalArticleSchema:
    """
    Costruisce e restituisce un oggetto GeopoliticalArticleSchema valido contenente
    dati di fallback sicuri e neutri. Evita crash della pipeline in caso di errori API irrecuperabili.
    """
    clean_date = published_at if published_at else "2000-01-01"
    
    return GeopoliticalArticleSchema(
        reasoning="Fallback automatico a causa del fallimento del modello o del validatore.",
        title=title[:120],
        summary="Errore di elaborazione automatica del testo. Notizia registrata con parametri di fallback.",
        published_at=clean_date,
        source_url=source_url,
        country_code="XX",
        latitude=0.0,
        longitude=0.0,
        companies_involved=[],
        tags=["Infrastrutture"],
        primary_category="Infrastrutture",
        sentiment="Neutrale",
        infrastructural_entities=[],
        relevance_level=1
    )
