# Every database log line printed twice

**Commit:** 86f9d83

**What happened:** Each message from `DatabaseManager` appeared twice in the cron log.

**Root cause:** `src/database/db.py` attached its own `StreamHandler` to its logger at import time. `main.py` also configures the root logger, so each record was emitted by both handlers.

**Fix:** Removed the handler setup from `db.py`. Entry points configure logging (`main.py` already did; `app.py` now calls `logging.basicConfig` too).

**Lesson:** Library modules should only call `logging.getLogger(__name__)`. Handlers and levels belong to the entry point.
