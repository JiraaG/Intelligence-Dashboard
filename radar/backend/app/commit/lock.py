"""Scritture vault atomiche con sidecar FileLock permanente.

Pattern: temp sibling → flush + fsync → ``os.replace`` → fsync directory
(best-effort). Il file ``{path}.lock`` non viene unlink-ato al release
(evita race su Windows e lascia evidenza del lock). Funzione sync: i caller
async usano ``asyncio.to_thread``.

SoT:
    docs/02 persistence; runbook outbox (vault atomico).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import cast

from filelock import FileLock

logger = logging.getLogger("radar.commit.lock")


class PermanentFileLock(FileLock):
    """FileLock che rilascia il lock OS **senza** cancellare il sidecar ``.lock``.

    ``filelock>=3.x`` esegue ``unlink()`` in ``_release``; qui il ``.lock`` resta
    permanente sul filesystem dopo lo unlock.
    """

    def _release(self) -> None:
        """Unlock + close fd; non cancella ``lock_file`` dal disco."""
        fd = cast("int | None", self._context.lock_file_fd)
        self._context.lock_file_fd = None
        if fd is None:
            return

        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)
            return

        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _fsync_directory(directory: Path) -> None:
    """Fsync della directory parent (durability del rename); ignora OSError (Windows)."""
    try:
        dir_fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def _atomic_write(target_path: Path, content: str) -> None:
    """Scrive ``content`` in ``target_path`` via temp + fsync + ``os.replace``.

    Il temp vive nella stessa directory del target (rename atomico sullo stesso FS).
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_path = target_path.parent / f".{target_path.name}.tmp.{os.getpid()}"

    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temp_path, target_path)
        _fsync_directory(target_path.parent)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as exc:
                logger.debug("Impossibile rimuovere il file temporaneo %s: %s", temp_path, exc)


def write_file_with_lock(file_path: str, content: str) -> None:
    """Scrive ``content`` in ``file_path`` in modo atomico sotto ``PermanentFileLock``.

    - Crea le directory parent se mancanti.
    - Scrive su sibling temporaneo, flush + fsync, poi ``os.replace``.
    - Fsync della directory parent dove supportato.
    - Sidecar ``{file_path}.lock`` permanente (mai unlink dopo release).
    - Sincrona: da async usare ``asyncio.to_thread`` (come in ``outbox.py``).

    Raises:
        Exception: errori di lock/IO — loggati e ri-lanciati.
    SoT:
        docs/02; runbook outbox.
    """
    target_path = Path(file_path)
    lock_path = str(target_path) + ".lock"
    lock = PermanentFileLock(lock_path, timeout=10.0)

    try:
        with lock:
            _atomic_write(target_path, content)
    except Exception as exc:
        logger.error("Errore critico durante la scrittura con lock sul file %s: %s", file_path, exc)
        raise
