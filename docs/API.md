# API

Base path `/api/v1`. JSON in and out. Interactive docs at `/docs` (switched off in production). Every response carries `X-Request-ID` and `Server-Timing: app;dur=<ms>`.

## One error shape

Every failure, whatever its cause, is:

```json
{ "error": { "code": "scheme_not_found", "message": "There is no such scheme.", "request_id": "…" } }
```

A request that fails validation adds `details`: a list of `{loc, message, type}` that says **where** a field failed and never what was submitted (it may be personal). An unexpected failure is a generic 500 with no internals; the full detail is in the log under the same `request_id`. The shape was kept (and not wrapped in `{success, data, error}`) because every client and test already uses it, it is consistent across all endpoints, and a wrapper would change every response for no gain (ADR in `DECISIONS.md`).

| Code | Status | Meaning |
| --- | --- | --- |
| `question_empty`, `question_too_long` | 422 | The question is missing or longer than `ASSISTANT_MAX_QUESTION_CHARS` |
| `rate_limited` | 429 | Too many questions from one address; `Retry-After` says how long |
| `assistant_not_configured` | 503 | No `GEMINI_API_KEY` on the server |
| `index_empty`, `index_unavailable` | 503 | The document index is empty or cannot be read |
| `payload_too_large` | 413 | The request body is above `MAX_REQUEST_BODY_BYTES` (default 64 KiB); it is refused before it is read |
| an unforeseen model failure | 500 | A failure code nobody planned for. Not the model being down, busy, slow or refusing our key: those give the passages instead (see below) |
| `scheme_not_found`, `unknown_scheme` | 404 | No such scheme or programme |
| `unknown_track`, `unknown_question`, `invalid_answer` | 422 | An eligibility request names something that does not exist; the answer's value is never echoed |
| `schemes_unavailable` | 503 | The records failed their checks when loaded (logged in full, shown to nobody) |
| `admin_denied` | 401 | The admin token is missing or wrong |
| `not_found` | 404 | Unknown address, or the admin page when no `ADMIN_TOKEN` is configured |

When the language model is busy, down, times out, returns unusable output, or **refuses our key or request** (`llm_auth`, `llm_rejected`: an operator problem the citizen cannot fix), `POST /assistant/ask` does **not** fail: it returns `200` with `fallback: true` and the best-matching passages (see below). The operator sees the cause on the admin page (`assistant.recent_failures`, `provider.circuit`), not the citizen.

## Caching

| Endpoint | Cache-Control | Notes |
| --- | --- | --- |
| `GET /schemes`, `/schemes/{id}`, `/budget`, `/sources` | `no-cache` + `ETag` | Keep a copy, ask every time; `If-None-Match` gets `304` with no body when unchanged. Large replies are gzip-compressed. |
| `POST /schemes/{id}/eligibility`, `POST /assistant/ask` | `no-store` | They describe one person |
| `GET /health`, `GET /health/ready` | `no-store` | |
| `GET /admin/*` | `no-store` | |

## Endpoints

### `GET /health`
Liveness: `{status, service, version, environment, timestamp, uptime_seconds}`. Touches no dependency; it says the process is up.

### `GET /health/ready`
Readiness, part by part: `{status, timestamp, components{records, index, assistant_model, ingestion}}`, each component `{status: ok|degraded|down|off, detail}`.

| Component | `ok` | `degraded` | `down` / `off` |
| --- | --- | --- | --- |
| `records` (schemes, programmes, budget) | loaded | | `down`: failed its checks. The only thing that makes the whole answer `503 unavailable` |
| `index` (official documents) | readable and not empty | empty or unreadable | |
| `assistant_model` | key set, circuit closed | circuit open: paused after repeated failures (`detail` names the last cause) | `off`: no key |
| `ingestion` | idle or running | the last run died holding the lock | |

The overall `status` is `ok`, `degraded` (the site works, one part is limited: HTTP 200) or `unavailable` (HTTP 503). A language-model outage is `degraded`, never `unavailable`: browsing, eligibility and the budget need neither the model nor the index. No path, key or question appears in it.

### `GET /schemes`
Everything in the catalogue as one list: schemes with an eligibility check and programmes/services that are read. Each item: `id, name, authority, level, state, sectors[], layout ("check"|"info"), kind, status, summary{en,bn,hi}, target, benefit, tracks[], deadline, source_ids[], last_verified`.

### `GET /schemes/{id}`
`layout: "check"` returns a scheme with its tracks, criteria (each with its quote), questions, documents and steps. `layout: "info"` returns a programme: `benefits, eligibility, exclusions, documents, steps` (each `{text, evidence[{source_id, quote, where}]}`), `apply{label,url,evidence}`, `not_stated[]`, `sources[]`, `status, status_note, last_verified, published_on, effective_on`. `404 scheme_not_found`.

### `POST /schemes/{id}/eligibility`
Body `{track, answers{field: value|null}}`. A skipped question is `null` or absent: an unknown, which can never make the result "eligible". Returns `{outcome: eligible|not_eligible|need_more_info, criteria[], unanswered[], checklist, disclaimer}`. Pure function of the rules and the answers; the answers are not stored or logged. A programme without a check answers `404 unknown_scheme`.

### `GET /budget`
Records with `budget_year, level, state, sector, kind, title, department, summary, meaning, figures[{basis, year, amount, unit, evidence}], statements[], sources[], not_actual_spending`. A figure is a `budget_estimate`, `revised_estimate` or `actual`; they are never mixed.

### `GET /sources`
The indexed documents with `document_date`, `verified_at`, `stale` (over 12 months), `verification_due`, `ocr`, `passages`.

### `POST /assistant/ask`
Body:

```json
{ "question": "…", "language": "auto|en|bn|hi",
  "source_ids": ["…"],      // optional: a hard limit to these documents (a chosen scheme)
  "history": ["…"],         // optional, at most 5 earlier questions; used only to find passages
  "sector": "health" }      // optional: nudges that sector's documents up, never hides others
```

Reply: `{answerable, language, text, claims[{text, citations[]}], citations[{number, source_id, title, url, page_start, section, quote, passage, highlights[], document_date, verified_at, stale, ocr}], not_stated[], warnings[], disclaimer, intent, fallback, model}`. Every claim rests on a quote that was found, word for word, in a retrieved passage, and every figure, month and address in it is in the quote. If the documents do not say, `answerable` is false and `text` says so. With `fallback: true` no explanation was written; `citations` are the best-matching passages exactly as the documents have them. Rate limited per address (`ASSISTANT_RATE_LIMIT_PER_MINUTE`).

### `GET /admin/knowledge`, `GET /admin/system`
Operator pages; need the `X-Admin-Token` header, and do not exist without `ADMIN_TOKEN`. Wrong tokens are counted per address and refused with `429` after `ADMIN_RATE_LIMIT_PER_MINUTE`.

- `knowledge`: per sector, the records, the documents behind them, their indexed passages, the old and due ones, and the ones not indexed; totals; the latest benchmark runs.
- `system`: per route, calls, errors, rate-limit refusals, `304`s, p50 and p95 latency; cache hit rates; whether the index is readable; the assistant's outcomes, fallback and error rates and recent failures (including ones the visitor never saw because the passages were shown instead); the language model's circuit breaker (`provider.circuit`: state, failure streak, last cause, times opened); how often verification removed what the model wrote; whether an ingestion is running or died holding its lock; the last execution traces (the intent, the records the router chose, the documents used, timings, whether verification dropped anything: never a question); the last ingestion run and why each rejected source was rejected.

## Security headers

Every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-site`, `Permissions-Policy`. CORS allows only the origins in `CORS_ORIGINS`.
