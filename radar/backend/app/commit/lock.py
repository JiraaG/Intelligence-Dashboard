import os
import logging
from filelock import FileLock

logger = logging.getLogger("radar.commit.lock")

def write_file_with_lock(file_path: str, content: str) -> None:
    """
    Scrive il contenuto in un file assicurandosi che non ci siano scritture concorrenti.
    Utilizza un file di lock parallelo gestito da filelock con timeout di 10 secondi.
    Crea automaticamente le directory genitore se mancanti.
    """
    # 1. Assicura la presenza della directory di destinazione
    target_dir = os.path.dirname(file_path)
    if target_dir and not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    lock_path = file_path + ".lock"
    lock = FileLock(lock_path, timeout=10.0)
    
    try:
        # 2. Acquisisce il lock ed effettua la scrittura del file
        with lock:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # 3. Rimuove il file di lock temporaneo una volta terminato
        try:
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except OSError as e:
            # Silenzioso: la rimozione del file di lock potrebbe fallire in rari casi di concorrenza estrema
            logger.debug(f"Impossibile rimuovere il file lock temporaneo {lock_path}: {e}")
            
    except Exception as e:
        logger.error(f"Errore critico durante la scrittura con lock sul file {file_path}: {e}")
        raise
