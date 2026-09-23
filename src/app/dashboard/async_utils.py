"""Helpers for invoking async Layer 2/3 code from synchronous Django views.

A single persistent background event loop is shared by all view calls so the
async SQLAlchemy connection pool is always used from the same loop.
"""

import asyncio
import threading

_loop = None
_loop_lock = threading.Lock()


def _get_shared_loop() -> asyncio.AbstractEventLoop:
    """Return the process-wide event loop, starting its worker thread on first use."""
    global _loop

    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            worker = threading.Thread(
                target=_loop.run_forever,
                name="agent-async-loop",
                daemon=True,
            )
            worker.start()

    return _loop


def run_async(coro):
    """Submit a Layer 2/3 coroutine to the shared loop and block until it finishes."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("run_async cannot be called from a running event loop.")

    future = asyncio.run_coroutine_threadsafe(coro, _get_shared_loop())
    return future.result()
