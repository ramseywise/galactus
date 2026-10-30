# Logging Standard — structured events, never free text

**Read the section for the repo you are in.** The shared rule across both: an event is a
dot-separated `module.action` name plus structured fields — never an interpolated sentence.
Interpolated text cannot be grouped, counted, or alerted on.

---

## TypeScript — pino

Repos: `diskoe`. The logger is `src/lib/logger.ts` (pino, `name: "diskoe"`), one default
export.

```ts
import logger from '@/lib/logger'

logger.info({ module: 'ingestion', subModule: 'processSource', n: rows.length }, 'source.processed')
logger.error({ module: 'api', err: String(e) }, 'recommendations.serve.failed')
```

- `module` / `subModule` are first-class — the dev formatter renders them as
  `[app:module:subModule]` and both are excluded from the extra-field dump.
- Level comes from `LOG_LEVEL`, defaulting to `info` when `APP_ENV` is `production` or
  `staging`, else `debug`. Do not hardcode a level at a call site.
- Production writes JSON to fd 1; dev writes the coloured formatter. Never add a second
  destination at a call site.

### Rules

- **No `console.*` on a request path or in library code.** `console` is acceptable in
  `src/core/cli/` mains and `src/evals/experiments/` scripts, where stdout *is* the
  interface and stderr carries progress — that is a deliberate exception, not a gap.
- Bind identifiers and counts as fields on the first argument; keep the message a stable
  event name so the same event is one group across runs.
- Beacon and fire-and-forget routes log server-side and still return their success status —
  `sendBeacon` cannot retry, so a 4xx silently drops the measurement rather than surfacing
  it (`diskoe/src/observability/README.md`).

---

## Python — structlog

### Setup

Always use `utils.logging` (structlog). Never use stdlib `logging` or `print()` in `src/`.
Assumes `src/utils/logging.py` exists in the project — check before using this pattern in a new project.

### Module pattern

```python
from utils.logging import get_logger

log = get_logger(__name__)  # one per file, module-level
```

### Entry point setup

Call once at startup — `main()`, app init, or notebook cell 1:

```python
from utils.logging import configure_logging

configure_logging()                    # dev: colored console
configure_logging(render_json=True)    # prod/CI: JSON lines
```

### Event naming

Dot-separated `module.action` — never free-form strings:

```python
log.info("sync.playlists", n=len(playlists))
log.info("train.gmm.fit", n_components=8, silhouette=sil)
log.info("train.classifier.skip", playlist=name, n_pos=n_pos, min_required=MIN_POSITIVES)
log.info("train.classifier.done", playlist=name, f1=f1, roc_auc=roc_auc)
log.error("etl.fetch.failed", error=str(exc), playlist_id=pid)
```

### Rules

- Bind counts and identifiers as structured fields — not f-string interpolation
- `debug` for per-item loops; `info` for phase transitions; `error` for caught exceptions
- Use `structlog.contextvars.bind_contextvars(run_id=...)` for request/session scope
- Notebooks: `setup_logging()` in the first code cell before any imports that log
- `train.py` and all ETL scripts use structlog — no `print()` exceptions
