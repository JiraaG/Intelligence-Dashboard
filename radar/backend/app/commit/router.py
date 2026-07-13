import os
import re
import hashlib
import logging
from app.core.config import OBSIDIAN_VAULT_PATH
from app.classification.validator import GeopoliticalArticleSchema

logger = logging.getLogger("radar.commit.router")

def initialize_vault_directories(vault_path: str = None) -> None:
    """
    Scansiona la directory del Vault di Obsidian e crea le 10 sottocartelle
    delle macro-categorie geopolitiche se non sono già presenti.
    """
    path = vault_path or OBSIDIAN_VAULT_PATH
    categories = ["Nucleare", "Energia", "Infrastrutture", "Geopolitica", "Economia", "Tecnologia", "Spazio", "Ambiente", "Salute", "Sicurezza"]
    
    logger.info(f"Inizializzazione delle directory del Vault su: {path}")
    
    try:
        # Crea la cartella principale del Vault se non esiste
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            logger.info(f"Creata directory radice del Vault: {path}")
            
        # Crea le sottocartelle delle macro-categorie
        for category in categories:
            category_path = os.path.join(path, category)
            if not os.path.exists(category_path):
                os.makedirs(category_path, exist_ok=True)
                logger.info(f"Creata sottocartella del Vault: {category_path}")
                
        logger.info("Inizializzazione directory Vault completata.")
    except Exception as e:
        logger.error(f"Errore durante l'inizializzazione del Vault su {path}: {e}")
        raise

def slugify_title(title: str) -> str:
    """
    Sanitizza in modo aggressivo il titolo per rimuovere i caratteri illegali e non sicuri
    sui filesystem Windows (NTFS/FAT), macOS (APFS) e Linux (ext4).
    Sostituisce i caratteri vietati con un trattino.
    """
    if not title:
        return "senza-titolo"
        
    # Rimozione caratteri non consentiti su Windows: \ / : * ? " < > |
    clean = re.sub(r'[\\/:*?"<>|]', "-", title)
    
    # Sostituisce spazi multipli, tab e trattini consecutivi con un unico trattino
    clean = re.sub(r"\s+", "-", clean)
    clean = re.sub(r"-+", "-", clean)
    
    # Rimuove trattini iniziali o finali e converte in lowercase
    return clean.strip("-").lower()

def get_article_file_path(article: GeopoliticalArticleSchema, vault_path: str = None) -> str:
    """
    Calcola il percorso semantico di salvataggio del file Markdown nel Vault di Obsidian.
    Struttura: /app/vault/{primary_category}/{country_code}/{filename}
    Nome file: {published_at}_{slugified_title}_{url_hash}.md
    """
    base_vault = vault_path or OBSIDIAN_VAULT_PATH
    
    # 1. Pulisce il titolo e calcola l'hash a 8 caratteri dell'URL per evitare collisioni
    slugified = slugify_title(article.title)
    url_hash = hashlib.md5(article.source_url.encode("utf-8")).hexdigest()[:8]
    
    filename = f"{article.published_at}_{slugified}_{url_hash}.md"
    
    # 2. Compila il percorso relativo alla macro-categoria e alla nazione
    # country_code viene forzato in maiuscolo (es. DE, US)
    country_folder = article.country_code.strip().upper()
    category_folder = article.primary_category
    
    target_dir = os.path.join(base_vault, category_folder, country_folder)
    
    # 3. Restituisce il percorso assoluto finale
    return os.path.join(target_dir, filename)
