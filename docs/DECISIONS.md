# Architecture decision records

Each record says what was decided, why, what it costs and what would change the decision. They describe what is built.

## ADR 1. Files that are checked, not a relational database

**Decided.** Programmes, schemes, budget records and sources are TOML files in the repository. The searchable text of the official documents is in ChromaDB. There is no SQL database and no ORM.

**Why.**

- Every statement carries a verbatim quote from an official document, and the loader and `catalogue-check` refuse a record whose figure is not in its quote. That guarantee is easy to keep with reviewed files in version control, where each change has an author, a diff and a test run, and hard to keep with rows edited in place.
- The records are a few hundred small documents, read far more often than written. They are loaded once into memory; there are no joins, no concurrent writers and no transactions that would call for a database server.
- Guest-first and no accounts: nothing about a visitor is stored, so there is no user table to design.
- It deploys as files plus one process.

**Costs.** No ad-hoc SQL queries; no admin screen that edits records (an administrator edits a file and runs the checks); a restart is needed to load changed records.

**Would change if** the product stores per-user data (saved schemes, reminders, accounts) or records are edited by many non-technical people at once. Then PostgreSQL behind the repository functions in `SchemeService` is the natural step; the record types in `app/domain/` are already the schema.

## ADR 2. A modular monolith

**Decided.** One FastAPI process with layers (`api` → `services` → `domain`, `core` beneath), and one React single-page app. No microservices, no message broker.

**Why.** One team, one deployment, and the only slow work (ingestion, model calls) is either run by a person from the command line or waits on a network call. Splitting would add network hops and failure modes with nothing to gain. The layering is enforced by convention and by tests: services never import from `api` or `cli`, and the API's start-up test fails if the heavy libraries are imported at start.

**Would change if** ingestion had to run on a schedule next to a busy API (then a worker process reading the same job file), or the assistant needed its own scaling (then a separate process behind the same routes).

## ADR 3. ChromaDB with a local multilingual embedding model

**Decided.** `intfloat/multilingual-e5-small` runs locally through ONNX Runtime (no PyTorch, no API key). ChromaDB stores 384-dimension vectors with metadata.

**Why.** Questions arrive in English, Hindi and Bengali and the documents are mostly English, so the embedding must work across languages. It runs on a CPU, costs nothing per question and sends no document text anywhere. The collection records the model's name and refuses to open with another, so vectors of different models are never compared.

**Measured limitation.** The model is small: the benchmark shows Bengali source recall at 0.85 (11 of 13 questions) against 1.00 for Hindi, and 2 of 4 Bengali questions missed in the live-answer run (small samples: `docs/BENCHMARKS.md`). A larger multilingual model would help, at the cost of a rebuild and slower queries (`ingest --rebuild` is the controlled path).

**Would change if** the corpus grew past what one machine's index serves comfortably (hundreds of thousands of passages).

## ADR 4. Search by the structured records first, then by meaning (the router), with keywords optional

**Decided.** A question is compared by meaning with the catalogue entries and budget records (the router). The documents behind the best matches are searched as well as the documents closest to the question, and the results are merged by reciprocal rank fusion. Earlier questions are added to a follow-up. The sector being viewed nudges its documents up. A keyword (BM25) ranking and a per-document cap exist but are **off by default**.

**Why.** Measured on 211 benchmark questions (`docs/BENCHMARKS.md`): the router alone raised source recall@5 from 0.89 to 0.96 and, with the follow-up history, to 0.98; Bengali (13 questions) went from 0.54 to 0.85. Keywords added nothing once the router was on and lowered the evidence hit rate (0.63 to 0.59); the cap lowered it too (0.61). A feature stays only if the numbers say so.

**Would change if** the benchmark were run on a larger corpus and showed keywords helping, which is one flag (`--features`, `DEFAULT_FEATURES`).

## ADR 5. Nothing a model writes reaches a user unless code has confirmed it

**Decided.** The model drafts claims with exact quotes; `grounding.verify` looks for each quote in the retrieved passages and for each figure, month and address in the quote; failed claims are dropped after one retry. Refusals, the disclaimer and warnings are fixed texts in three languages. If the model is down, the user is shown the best-matching passages exactly as the documents have them (`fallback`), never a made-up answer. Eligibility is a pure function of rules and answers; no model decides it.

**Why.** For government information a confident wrong answer is worse than none. This is the product's central promise and the reason for most of the structure above.

## ADR 6. Caching only what cannot go stale, and revalidating the rest

**Decided.**

- The list of indexed sources is kept until the index's change stamp changes. Every write by any process leaves a new stamp, so the copy is never older than the index.
- Public lists (`/schemes`, `/budget`, `/sources`) carry an `ETag` and `Cache-Control: no-cache`: the browser may keep a copy, but must ask every time, and the server answers `304` with no body if nothing changed. The reply is always recomputed, so a deadline that moved from "11 days left" to "10 days left" changes the hash and is sent in full.
- Personal replies (an answer, an eligibility result) are POSTs and are never cached (`no-store`).
- No answer is cached. A cached answer could outlive a changed document or deadline, and a question is rarely repeated exactly.

**Would change if** a measurement showed repeated identical questions were a large share of model calls; then a cache keyed by (question, index stamp, language) would be safe to add, because the stamp invalidates it.

## ADR 7. Ingestion is a command with jobs, not a request

**Decided.** Documents are fetched, checked, extracted, chunked, embedded and indexed by `python -m app.cli ingest`, never inside a request. It is idempotent (a source whose fingerprint is unchanged is skipped), version-aware (the fingerprint includes the bytes, the registry entry, the extractor and chunker versions and the embedding model), writes new passages before deleting stale ones, retries only transient network failures with exponential backoff, and records each source's state in `storage/jobs/ingest.json` for the admin page.

**Why.** It is slow, touches the network, and a person should confirm each source. A queue and workers would add infrastructure for a task a command already does safely.

**Would change if** uploads by visitors were added: then an upload endpoint would write a job file and a worker (the same code) would process it.

## ADR 8. The error envelope stays as it is; there is no `{success, data, error}` wrapper

**Decided.** Successful replies are the resource itself; every failure is `{"error": {code, message, request_id, details?}}` (`app/core/errors.py`). Request ids are in the `X-Request-ID` header and in every error body, not in a wrapper around successes.

**Why.** The shape is already consistent across all endpoints, the frontend and its tests are written against it, and a wrapper would change every response, every client type and every test for no new capability. HTTP status codes already say whether a call succeeded.

**Would change if** a client (a mobile app, a partner) needed one parsing path for success and failure. Then the wrapper belongs in a new `/api/v2` and the existing paths keep working.

## ADR 9. When the model fails, the citizen still gets the documents; the breaker and the time limit are ours

**Decided.** Every way the model can fail (down, busy, slow, a refused key, a rejected request, a reply that is not the requested shape) ends in `200` with `fallback: true` and the best-matching passages, exactly as the documents have them. The retry loop is in `GeminiClient`, not the SDK's: a doubling pause with jitter, `Retry-After` obeyed up to 10 s, a total deadline (`GEMINI_DEADLINE_SECONDS`, 50) under the 60 s the browser waits, and no retry of a wrong key or a bad request. A circuit breaker (`services/llm/resilient.py`) stops asking after `LLM_BREAKER_THRESHOLD` provider failures in a row and probes once after the cooldown.

**Why.** Before, an outage made every question wait up to about 91 s (45 s, twice, plus the SDK's own retry) while the browser gave up at 60 s, and a wrong or expired key showed the citizen an error although the answer to "what do the documents say" was already in hand. A citizen cannot fix a key. Showing them the official text, with the reason hidden from them and kept for the operator (`assistant.recent_failures`, `provider.circuit`, `GET /health/ready`), is always better than an error and is never an invented answer: nothing in the fallback is written by a model.

**Costs.** A bad key no longer announces itself to visitors, so the operator must look at `/admin` or the readiness endpoint (it is `degraded`). The breaker is per process: several API processes each learn of an outage separately.

**Would change if** the product needed to show the citizen *why* (a banner for an expired key), or ran many processes (then a shared breaker state belongs in the proxy or a small store).

## ADR 10. The index is protected by snapshots, a lock and reconciliation, not by transactions

**Decided.** There is no SQL database, so there are no transactions to wrap. The equivalent protections are: one ingestion at a time (a lock file with a heartbeat); a snapshot of the index, read back and compared, before any `--rebuild`, and `index-restore` to return to it; a source is "unchanged" only when the audit record *and* the index agree with the document (the record is written last, so a run that died half way is redone); `replace_source` writes new passages before removing old ones (a question mid-update sees the old or the new, never none); and a read-only `index-check` that compares index, records and registry and never deletes anything.

**Why.** The index is derived data, but it is also what every answer is made of, and one real corruption happened during development (two writers). The cheap, testable protections are the ones above, and each is tested by injecting the crash it guards against (`tests/test_ingest_interruptions.py`, `test_index_safety.py`).

**Would change if** user data were stored (saved schemes, reminders): then PostgreSQL with migrations, constraints, idempotency keys and optimistic locking become necessary, and the requirements in the reliability brief for them apply for the first time (see `RELIABILITY.md`, "Not covered").
