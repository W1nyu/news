"""OS-released lock shared by scheduled, CLI and browser collection."""
from contextlib import contextmanager
import os
from pathlib import Path

@contextmanager
def collection_lock():
    path=Path(__file__).resolve().parents[1]/'data/collection.lock'
    path.parent.mkdir(exist_ok=True)
    with path.open('a+b') as handle:
        if not path.stat().st_size: handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as error: raise RuntimeError('Collection already running') from error
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)
