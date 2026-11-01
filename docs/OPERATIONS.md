# Operations: setup, environment, deployment, health, rollback

## Local setup (Windows; on Linux or macOS use `.venv/bin/python`)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints.txt
copy .env.example .env          # then put GEMINI_API_KEY in .env
.\.venv\Scripts\python.exe -m app.cli ingest      # builds the index (the first run downloads the embedding model)

cd ..\frontend
npm ci
```

Run: `python -m uvicorn app.main:app --reload` (port 8000) and `npm run dev` (port 5173, proxies `/api`). The API reads `.env` only when it starts: restart it after changing a key or any data file.

## Environment variables (`backend/.env`; every one is documented in `backend/.env.example`)

| Variable | Default | What it does |
| --- | --- | --- |
| `APP_ENV` | `development` | `production` switches off `/docs` and refuses `CORS_ORIGINS=*` |
| `LOG_LEVEL` | `INFO` | |
| `CORS_ORIGINS` | the two local Vite origins | Comma list or JSON list of browser origins allowed to call the API directly |
| `DATA_DIR` | `backend/storage` | Downloaded documents, the index, the embedding model, job and benchmark records |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Changing it needs `ingest --rebuild`; the store refuses to mix models |
| `FETCH_TIMEOUT_SECONDS`, `MAX_DOCUMENT_MB` | 30, 25 | Limits for downloading an official document |
| `GEMINI_API_KEY` | none | Server-side only. Without it the assistant is off and the rest works |
| `GEMINI_MODEL`, `GEMINI_TIMEOUT_SECONDS`, `GEMINI_MAX_OUTPUT_TOKENS`, `GEMINI_THINKING_LEVEL`, `GEMINI_BASE_URL` | see the file | The language model's settings |
| `GEMINI_DEADLINE_SECONDS` | 50 | The most one question waits for the model in all, retries included. Keep it under the 60 s the browser waits |
| `LLM_BREAKER_THRESHOLD`, `LLM_BREAKER_COOLDOWN_SECONDS` | 5, 30 | After this many provider failures in a row the model is not asked for the cooldown, and visitors get the matching passages at once. One probe then tests recovery |
| `ASSISTANT_MAX_QUESTION_CHARS`, `ASSISTANT_RATE_LIMIT_PER_MINUTE` | 500, 20 | Cost and abuse limits on questions |
| `MAX_REQUEST_BODY_BYTES` | 65536 | Larger request bodies get HTTP 413 before they are read |
| `ADMIN_TOKEN` | none | Opens `/api/v1/admin/*` and the `/admin` page. None means they do not exist. Use a long random string; never put it in the frontend |
| `ADMIN_RATE_LIMIT_PER_MINUTE` | 10 | Wrong admin-token attempts per client per minute |
| `CACHE_ENABLED` | `true` | Keep the list of indexed sources until the index changes |
| `COMPRESS_RESPONSES` | `true` | gzip for JSON replies of 1 KB or more |
| `ACCESS_LOG` | `true` | One line per request: method, route, status, milliseconds. Never the query string or body |

Frontend: `VITE_API_BASE_URL` (empty when the API is on the same origin); `API_PROXY_TARGET` for the dev proxy. Nothing secret reaches browser code.

## Commands

| Task | Command (from `backend/`) |
| --- | --- |
| Check a change | `python -m ruff check . && python -m ruff format --check . && python -m mypy && python -m pytest` |
| Frontend | `npm run lint && npm run typecheck && npm test && npm run build` (from `frontend/`) |
| Check one source | `python -m app.cli verify <id>` |
| Fetch and index | `python -m app.cli ingest [id ...]` (idempotent; transient failures are retried) |
| Rebuild the index | `python -m app.cli ingest --rebuild` (first takes a snapshot and reads it back; see Backup and recovery) |
| Do the index, the records and the registry agree? | `python -m app.cli index-check` (read-only; changes nothing) |
| List or restore index snapshots | `python -m app.cli index-backups` · `python -m app.cli index-restore [NAME]` (stop the API first) |
| Release gate: every check, with an honest status for each | `python scripts/reliability.py [--browser] [--live]` |
| Fault injection: make the model fail in a chosen way | `python scripts/stub_provider.py --status 503` and start the API with `GEMINI_BASE_URL=http://127.0.0.1:9999` |
| Quotes are still in the documents | `python -m app.cli catalogue-check` and `schemes-check` |
| What each sector holds | `python -m app.cli kb-health` or `python -m app.cli catalogue` |
| AI benchmark | `python -m app.cli eval [--strategy dense\|knowledge] [--features …] [--hint right\|wrong\|none] [--answer --limit N]` |
| API benchmark | `python scripts/benchmark_api.py` |
| Load test | `python scripts/loadtest.py --users 20 --seconds 20` |
| Tests that need the internet, the embedding model or a Gemini key | `python -m pytest -m live` |

Continuous integration (`.github/workflows/ci.yml`) runs the checks above, and fails if an `.env` file or a key-shaped string is committed. It needs this folder to be the root of its repository.

## Deployment

One FastAPI process (`uvicorn app.main:app`) behind a reverse proxy that also serves the built frontend (`npm run build` makes `frontend/dist`). The frontend and API share an origin, so there is no CORS. The index and `storage/` live on the API's disk; `ingest` runs on the same machine, by a person or a scheduler, and the running API notices the new index by itself (the change stamp), with no restart. The records in `backend/data/` load when the API starts: restart after changing them.

What the host must provide: HTTPS; `Content-Security-Policy` for the frontend (the API sets the security headers listed in `API.md` for its own replies); a process manager; a persistent `DATA_DIR`. A hard shared rate limit across several API processes belongs at the proxy (the built-in limit is per process).

### Free hosting: a Hugging Face Space (`deploy/huggingface/`)

The API needs about **980 MB of memory** after its first question (measured: the embedding model and the index; 62 MB before), so Render's free instance (512 MB) cannot run it. A free Hugging Face Space (Docker, 16 GB, an HTTPS address of its own, no card) can. `FRONTEND_DIR` makes the API serve the built website, so one container is the whole product.

1. Create a Space (SDK: Docker) and a token with write access. Put the token in the `HF_TOKEN` environment variable.
2. `python deploy/huggingface/stage.py --upload OWNER/NAME` copies the sources and `backend/storage/chroma` (the index built by `ingest`) to a clean folder, **refuses to continue if an `.env` file or a key-shaped string is in it**, and pushes it. Hugging Face builds the `Dockerfile`: it builds the website, installs the pinned dependencies, downloads the embedding model, and runs `search` on the index, which fails the build if the index is empty or unreadable.
3. In the Space's settings add **secrets** `GEMINI_API_KEY` and `ADMIN_TOKEN`, and variables `GEMINI_MODEL` (one your key can use: run `assistant-check` with it first) and optionally `CORS_ORIGINS`. Settings are never in the image.
4. Open `https://OWNER-NAME.hf.space` itself, not the page on huggingface.co: the API sends `X-Frame-Options: DENY`, and the microphone does not work in an embedded frame.

Limits to know: the Space's disk is **not persistent** (what is not in the image is lost on restart, which is fine here because nothing is stored: SPEC AC9), a free Space **sleeps after a period without visits** and takes about a minute to wake, and the index is the one built on the developer's machine, so to refresh the documents run `ingest` locally and upload again. A public Space is open to anyone: the built-in limit of 20 questions per minute per visitor protects the Gemini quota only so far, so watch the key's usage.

## Health and monitoring

- `GET /api/v1/health`: liveness (the process is up).
- `GET /api/v1/health/ready`: readiness by part (`records`, `index`, `assistant_model`, `ingestion`). `200` with `ok` or `degraded`; `503` only if the records cannot load. A model outage is `degraded`, so a load balancer should poll *this*, and never take the site out of service because the model is down.
- `/admin` (needs `ADMIN_TOKEN`): knowledge-base coverage by sector, and system health (request counts, errors and latency per route, cache hit rates, whether the index is readable, the language model's recent failures, the last answers' traces, the last ingestion run and why a source was rejected).
- Logs: one structured line per request with its `X-Request-ID`; the same id is in every error body and every log line of that request.
- Nothing logs a question, a passage, a model reply, a questionnaire answer or an upload (SPEC AC9).

## Backup and recovery

What there is to lose, and how each part is protected:

| Data | Where | Protection |
| --- | --- | --- |
| Scheme, programme and budget records, the source registry | `backend/data/` (files in git) | Version control; every change is checked against its documents (`catalogue-check`, `schemes-check`) and for conflicts between records. Roll back with git |
| The document index | `storage/chroma/` | Derived data: `ingest` rebuilds it from the registry. `ingest --rebuild` first copies it to `storage/backups/chroma-<time>` **and opens the copy to compare its contents with the original**; if they differ, the rebuild does not start. The newest 3 snapshots are kept |
| Downloaded documents and audit records | `storage/raw/`, `storage/parsed/` | Written atomically (temporary file, then rename); `index-check` compares them with the index |
| Visitors' questions and questionnaire answers | nowhere | Never stored (SPEC AC9): there is nothing to back up or to lose |

**A rebuild that went wrong** (the network was down, so every source was rejected and the index is empty):

1. `python -m app.cli index-check` shows what is missing.
2. Stop the API (on Windows an open index cannot be replaced).
3. `python -m app.cli index-restore` puts the newest snapshot back and keeps the index it replaced as `chroma.replaced-<time>` (delete it once you have looked). The running API notices the new index by its change stamp.

Restoring has been tested here by building an index, snapshotting it, destroying it and restoring it, then comparing passage counts and searching it (`tests/test_index_safety.py`, `tests/test_cli_index_safety.py`). It has **not** been tested on a second machine or against a network drive.

**Two ingestions at once** are refused (`error: Another ingestion is already running`, exit status 3). The lock is a file in `storage/jobs/` refreshed every 22 s by a heartbeat; if the process holding it is killed, it expires 90 s later and the next run takes over. If `ingest` stopped without finishing, the admin page shows the lock as `interrupted`.

## Rollback

| What went wrong | Roll back by |
| --- | --- |
| A code change | Redeploy the previous commit; `storage/` is compatible (a changed fingerprint just makes `ingest` re-process) |
| A bad record file | Revert the file; the API refuses to load a record that fails its checks and says which (`schemes_unavailable`, logged in full), while the rest keeps working |
| A bad ingest | A rejected source never touches the index. To undo an accepted one, revert the registry entry and run `ingest`; for a clean slate, `ingest --rebuild` |
| A damaged index (a crash during a write, "Failed to apply logs to the hnsw segment writer") | `python -m app.cli ingest --rebuild` (it snapshots first). The index is derived data. This happened once during development, after an ingest was killed mid-write; the lock now prevents two writers |
| A rebuild that left the index empty or short | `python -m app.cli index-restore` (stop the API first) |
| The model is down or its key was refused | Nothing to roll back: visitors get the matching passages, browsing and eligibility are unaffected. Fix the key or wait; the breaker probes by itself and closes when the model answers |
| A suspected leaked key | Rotate it at the provider, edit `backend/.env`, restart the API |
