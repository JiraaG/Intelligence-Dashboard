import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(
    log_level: int = logging.INFO,
    log_file: str = "logs/radar.log",
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 5
) -> None:
    """
    Configura il logging centralizzato e strutturato.
    Crea un console handler ed un rotating file handler.
    """
    # Assicura che la directory dei log esista
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Formattatore centralizzato e strutturato
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Rimuove handler preesistenti per evitare duplicati
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console Handler (Stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        # Fallback nel caso in cui non ci siano permessi di scrittura sul file
        logging.warning(f"Impossibile inizializzare il RotatingFileHandler su {log_file}: {e}")

    logging.info("Logging centralizzato configurato con successo.")
