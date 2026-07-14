# lock.py — Atomic vault writes with permanent FileLock sidecar

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import cast

from filelock import FileLock

logger = logging.getLogger("radar.commit.lock")


class PermanentFileLock(FileLock):
    """
    FileLock che rilascia il lock OS senza cancellare il file sidecar.
    filelock>=3.x esegue unlink() in _release; qui il .lock resta permanente.
    """

    def _release(self) -> None:
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
    """Best-effort directory fsync; ignore OSError (common on Windows)."""
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
    """
    Scrive content in file_path in modo atomico sotto FileLock.

    - Crea le directory parent se mancanti.
    - Scrive su sibling temporaneo nella stessa directory, flush + fsync, poi os.replace.
    - Fsync della directory parent dove supportato (OSError ignorato su Windows).
    - Il sidecar ``{file_path}.lock`` resta permanentemente sul filesystem (mai unlink dopo release).
    - Funzione sincrona: i caller async possono usare asyncio.to_thread.
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
