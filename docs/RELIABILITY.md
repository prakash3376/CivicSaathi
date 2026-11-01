# Reliability: what can fail, how each failure is contained, and what is not covered

CivicSaathi tells people what government schemes say. A failure must never mislead, lose what a person entered, leave the page stuck, or show a model's guess as an official statement. This file records the failures that were **found by reading and running the code** (not a list of failures that might exist), what was done about each, how it was tested, and what remains.

Run the whole gate with `python scripts/reliability.py` (from `backend/`; add `--browser` for the real-Chrome journeys and `--live` for the tests that call Gemini). It runs every check, gives each a status of PASS, FAIL, DEGRADED, BLOCKED or NOT TESTED, and writes `storage/reliability/report-<time>.md`. It says "RELEASE-READY" only when every P0 and P1 step passed; a step that could not run is BLOCKED, never a pass.

Severity: **P0** serious harm (misleading government information, data loss, outage); **P1** a critical journey broken or a wrong eligibility outcome; **P2** degraded with a way around; **P3** minor.

## What this application is (and so which failures exist)

| The brief assumes | CivicSaathi has | Consequence |
| --- | --- | --- |
| A SQL database, ORM, transactions, migrations | Checked TOML files for records; ChromaDB for the document index (derived data) | Transactions, foreign keys and migrations do not apply. The index is protected differently (ADR 10) |
| User profiles and saved data, several devices | No accounts. Questionnaire answers and the chat live in the browser's memory only (SPEC AC9) | Nothing of a person's is stored, so nothing can be lost or overwritten on the server, and multi-tab conflicts cannot arise on the server |
| Document upload by users | None. Documents enter only when a person adds a registry entry and runs `ingest` | Upload quarantine and states do not apply. The ingestion pipeline's own failures do (below) |
| Background workers and a queue | One command (`ingest`) with a job record | Leases, retries and stuck-job detection are applied to that |

## Failure-mode register

Every row was found in the code or by running it. "Test" names the file; the failure was injected, not assumed.

| # | Pri | Component | What could go wrong | Root cause | Protection | Test |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | P0 | Index writes | Two `ingest` runs at once corrupt the index (it happened once) | No cross-process lock | Lock file with a heartbeat lease; a killed holder expires after 90 s and is taken over by exactly one successor (atomic rename) | `test_index_safety.py::TestLock` (8 threads race: one winner), `test_cli_index_safety.py` |
| 2 | P0 | `ingest --rebuild` | The index is emptied first; if the network is down every source is rejected and visitors have nothing to search | The rebuild deletes before it fetches | A snapshot is taken and **read back and compared** first; if the copy differs, the rebuild does not start. `index-restore` puts it back | `test_index_safety.py::TestBackup`, `test_cli_index_safety.py` (rebuild with every source failing, then restore, then compare) |
| 3 | P0 | Eligibility input | A 400-digit integer as an income answer returned HTTP 500 | `math.isfinite()` converts an int to float and overflows | Integers are never converted; magnitude bounded at 10^15; all refused as `invalid_answer` | `test_eligibility_properties.py` (found by a probe, then pinned) |
| 4 | P1 | AI client | During a model outage each question waited up to about 91 s while the browser gave up at 60 s | 45 s timeout × 2 attempts plus the SDK's own retry; no overall deadline | Own retry loop: total deadline 50 s, jittered doubling pause, `Retry-After` obeyed (up to 10 s), no retry of a wrong key; each attempt gets only the time left | `test_gemini.py::TestHowRetriesWait` |
| 5 | P1 | AI service | Every question during an outage still paid for failed calls | No circuit breaker | Breaker: after 5 provider failures in a row the model is not asked for 30 s, then one probe; a refused key or a blocked prompt never opens it | `test_resilient.py`, `test_provider_outage.py::TestTheCircuitBreakerSavesEveryoneTheWait` |
| 6 | P1 | AI service | A wrong or expired key showed the citizen a 503, though the matching documents were already found | `llm_auth` / `llm_rejected` were re-raised | They degrade to the passages like any outage; the operator still sees the cause | `test_provider_outage.py` (every one of 20 failure modes ends in the passages, never a 500) |
| 7 | P1 | Ingestion | A run that died while replacing a changed document could be called "unchanged" on the next run, leaving old and new passages mixed | "Unchanged" trusted the index's first passage alone | "Unchanged" needs the audit record (written last) **and** the index to match the document | `test_ingest_interruptions.py` (failed before the fix) |
| 8 | P1 | API | A huge request body was read in full | No size limit | `BodyLimitMiddleware`: 413 before reading a declared length; chunked bodies counted and stopped | `test_body_limit.py` |
| 9 | P1 | Frontend | A render error or a page whose code could not be fetched (offline, new deploy) showed the router's default error screen, or nothing | No error boundary or `errorElement` | Route error page with the header kept, a retry that works for a failed code fetch, and section boundaries so a chat crash leaves the rest | `*.resilience.test.tsx`; `e2e/resilience.mjs` |
| 10 | P1 | Data accuracy | Two records could give different figures for one measure and year, or one programme twice | Only each record was checked, never records against each other | `check_consistency` (duplicates, conflicting figures, impossible actuals and dates), part of `catalogue-check`. **The shipped data has no findings** | `test_consistency.py` |
| 11 | P2 | Ingestion | A domain error in one source stopped the whole run and left its job "running" | Not caught per source | Reported as a rejection with its reason; a bug marks the job `failed` before it propagates | `test_ingest_interruptions.py::TestOneFailingSourceNeverStopsTheRest` |
| 12 | P2 | Ingestion | `ingest` never released the index, so it could not be moved or restored in the same process | The store was not closed | Closed in a `finally` | `test_cli_index_safety.py` |
| 13 | P2 | Operations | A model failure shown to the visitor as passages was invisible to the operator | Only raised errors were counted | `note_failure`; fallback and error rates; the breaker's state on `/admin/system` and `/health/ready` | `test_admin.py`, `test_provider_outage.py::TestTheOperatorCanSeeWhatTheCitizenDidNot` |
| 14 | P2 | Operations | Only liveness existed, so a probe could not tell "dead" from "model down" | One health endpoint | `/health/ready` by component; only unloadable records make it 503 | `test_provider_outage.py::TestReadiness` |
| 15 | P2 | Frontend | An answer arriving after "new conversation" was applied and handed to the voice flow | `useChat.ask` returned the late answer | Returns `null` when the chat was cleared or left | `useChat.resilience.test.tsx` |
| 16 | P2 | Frontend | No sign that the browser was offline | None | Localised notice, removed on reconnect | `AppLayout.resilience.test.tsx`; `e2e/resilience.mjs` |
| 17 | P2 | Disk | Index, records and registry could disagree after a crash with nothing to say so | No reconciliation | `index-check`: orphans, missing sources, passage counts that differ, old temp files. Read-only | `test_ingest_interruptions.py::TestReconciliation` |

### Checked and found already sound (no change made)

- **Double submission and stale answers in the chat and the eligibility form**: the pending state and the cleared question box already prevented them; tests now pin it (`ChatPage.resilience.test.tsx`, `EligibilityPage.resilience.test.tsx`). The agent that wrote those tests reported that they fail when the guard is removed; that was not repeated independently.
- **A failed eligibility check keeps every answer** and a retry sends the same body.
- **Unknown never becomes "not met"**, and an age outside a rule never gives "eligible": now a property over generated rules, not just examples; four deliberate engine bugs were all caught (`test_eligibility_properties.py`).
- **Errors never echo what was submitted**; unexpected exceptions return a generic 500 with the request id and log the detail.
- **Dates are separate fields**: a record has `published_on`, `effective_on` and `last_verified`; a document has its own date and a `verified_at`; "an old document checked today" is never shown as new (`test_freshness.py`, `test_consistency.py`).
- **Citations point at a real passage**: every claim's quote is found word for word in a retrieved passage and every figure, month and address in the claim is in the quote, or the claim is dropped (ADR 5).

## How the checks were verified to be able to fail

A test that cannot fail proves nothing, so the important ones were attacked:

- **Eligibility properties**: four bugs were put into the engine one at a time (unknown treated as false; `lt` made `lte`; an empty waiver counted as granted; a failed rule downgraded to unknown). The properties caught all four, and the file was restored byte for byte afterwards.
- **Interrupted ingestion**: the half-written-source test, the failed-job test and the domain-error test **failed before** their fixes and pass after.
- **The release gate**: its first run failed on a real mistake (a new setting missing from `.env.example`), its second on slow-machine timeouts in the existing frontend tests, and its verdict logic has its own tests (`tests/test_reliability_runner.py`), including that a run that executed no tests is a FAIL and a tool that is missing is BLOCKED.

The frontend test suite was also made less fragile on a busy machine: the vitest per-test limit (5 s) and Testing Library's wait (1 s) were raised (`vite.config.ts`, `src/test/setup.ts`), because the slowest existing accessibility test takes 4.8 s on an idle machine and failed whenever the machine was busy. Nothing asserts on speed, so this changes when a slow page is reported as broken, not what counts as broken.

## For each protection: what if the protection itself fails?

| Protection | If it fails |
| --- | --- |
| Ingest lock | A stale lock from a killed run is taken over after 90 s (a person can also delete `storage/jobs/ingest.lock`). If the filesystem's modification times are unreliable (some network drives), a live holder could look dead: run ingestion on a local disk |
| Snapshot before rebuild | If the snapshot cannot be made or does not match, the rebuild **does not start** (it fails closed). If disk space runs out during the copy, the partial copy is removed |
| Restore | Refuses an empty or missing snapshot; moves the current index aside instead of deleting it; fails with "stop the API" if the index is open (it cannot be moved on Windows) and changes nothing |
| Circuit breaker | If it wrongly stays open the model is not asked until the cooldown ends and one probe succeeds; visitors get passages meanwhile. A bug in the breaker itself is not counted as a provider failure and frees the probe |
| Retry deadline | If the SDK or network ignores a timeout the browser's own 60 s limit still ends the wait (the page shows the error with a retry) |
| Body limit | A body that passes the limit by chunks is stopped at the limit; if the response had already started the connection is cut |
| Error boundary | If the boundary itself throws, a second `errorElement` on the root shows the generic error page; the header and menu are gone but the page is not blank |
| Consistency check | It finds only what it knows to look for (duplicates, figures, dates). A wrong figure that no other record contradicts is caught only by `catalogue-check` against the document |
| Reconciliation | Read-only: it cannot damage anything, and it cannot fix anything either |

## What is not covered (and why)

- **Database transactions, migrations, idempotency keys, optimistic locking, multi-device conflicts, document upload, quarantine and per-user privacy**: the application has none of these features. They become requirements if accounts or uploads are added; ADR 1 and ADR 10 say what would change.
- **Contradiction between two retrieved passages at answer time**: the catalogue is checked for conflicting figures, but when two *documents* give different values for the same rule, the answer does not yet say "the official sources appear inconsistent". It shows each claim with its own citation; it does not compare across them. Not built.
- **Restore on another machine, behaviour under load during a rebuild, memory under load**: not tested.
- **A stray unhandled promise rejection in the browser** is not caught globally (no client-side error reporting exists; adding one would send data off the device).
- **Multiple API processes**: the breaker, the rate limiters and the request metrics are per process.
- **Provider `Retry-After` as an HTTP date** is not parsed (the doubling pause is used).
- **Dependency vulnerability scanning and malware scanning** are not run (no scanner is installed here); there are no uploads to scan.
- **The new Bengali and Hindi texts** (error pages, the offline notice, the model-failure message) are drafts by a non-native speaker and need a native speaker's review.
- Some official documents are unverified or old (the knowledge-base report lists them); the system shows their age but cannot know that a rule has changed since.

## Commands

| Task | Command |
| --- | --- |
| Everything, with a verdict | `python scripts/reliability.py [--browser] [--live]` (from `backend/`) |
| One area | `python scripts/reliability.py --only provider` (also: `grounding`, `eligibility`, `index-safety`, `consistency`, `security`, `frontend`, `browser`) |
| The failure tests only | `python -m pytest tests/test_provider_outage.py tests/test_index_safety.py tests/test_cli_index_safety.py tests/test_ingest_interruptions.py tests/test_body_limit.py tests/test_resilient.py tests/test_eligibility_properties.py tests/test_consistency.py` |
| Frontend failure tests | `npm run test:reliability` (from `frontend/`) |
| Real-Chrome journeys | `node frontend/e2e/journey.mjs <url>` and `node frontend/e2e/resilience.mjs <url>` (needs `puppeteer-core`, `axe-core`; see the files) |
| Make the model fail on purpose | `python scripts/stub_provider.py --status 429 --retry-after 3`, then start the API with `GEMINI_API_KEY=x GEMINI_BASE_URL=http://127.0.0.1:9999` |
