# mypy: ignore-errors
import logging
import os
import threading
import traceback

log = logging.getLogger("thread_tracer")

THREAD_SNAPSHOT_INTERVAL = int(os.environ.get("THREAD_SNAPSHOT_INTERVAL", "30"))

_original_start = threading.Thread.start
_original_run = threading.Thread.run
_patched = False


def _caller_site():
    """Return file:line of the first frame outside threading internals."""
    last = ""
    for line in traceback.format_stack():
        if "threading" not in line and "thread_tracer" not in line:
            last = line.strip()
    return last.split("\n")[0].strip()


def _patched_start(self):
    caller = _caller_site()
    log.warning(
        "THREAD_EVENT=start name=%s daemon=%s count=%d caller=%s",
        self.name,
        self.daemon,
        threading.active_count(),
        caller,
    )
    _original_start(self)


def _patched_run(self):
    try:
        _original_run(self)
    finally:
        log.warning(
            "THREAD_EVENT=exit name=%s count=%d",
            self.name,
            threading.active_count() - 1,
        )


def _snapshot_loop(interval):
    while True:
        threads = threading.enumerate()
        log.warning(
            "THREAD_SNAPSHOT count=%d names=%s",
            len(threads),
            [t.name for t in threads],
        )
        threading.Event().wait(interval)


def install():
    """Monkey-patch Thread to log start/exit events and start a periodic snapshot."""
    global _patched
    if _patched:
        return
    _patched = True

    threading.Thread.start = _patched_start
    threading.Thread.run = _patched_run

    snapshot = threading.Thread(
        target=_snapshot_loop,
        args=(THREAD_SNAPSHOT_INTERVAL,),
        daemon=True,
        name="thread-tracer-snapshot",
    )
    _original_start(snapshot)  # use original to avoid logging our own thread

    log.warning(
        "Thread tracer installed (snapshot every %ds, pid=%d)",
        THREAD_SNAPSHOT_INTERVAL,
        os.getpid(),
    )
