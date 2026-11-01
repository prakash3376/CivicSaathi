# Architecture

How CivicSaathi is put together, and the conventions to keep as it grows. This file covers the code; the rest of the architecture is in its own files:

| File | What it holds |
| --- | --- |
| [DATA_MODEL.md](DATA_MODEL.md) | The entities (sources, entries, schemes, budget records, passages) and their relations, as an ER diagram; why there is no SQL database |
| [DATA_FLOW.md](DATA_FLOW.md) | A document becoming evidence; a citizen browsing; a citizen asking (Mermaid) |
| [API.md](API.md) | Endpoints, request and reply shapes, error codes, caching |
| [DECISIONS.md](DECISIONS.md) | Architecture decision records with their measurements |
| [OPERATIONS.md](OPERATIONS.md) | Setup, environment variables, deployment, health, rollback |
| [BENCHMARKS.md](BENCHMARKS.md) | Measured before and after: API latency, bundle size, retrieval quality |
| [PORTAL.md](PORTAL.md) | The home page, sectors, search, budget and what is not built |
| [RELIABILITY.md](RELIABILITY.md) | What can fail and how each failure is contained: the failure-mode register, protections, tests, and what is not covered |

The rest of this file is the original, written after Phase 5; where it says a package is "planned" it is. Product requirements live in [SPEC.md](../SPEC.md); the data sources are described in [DATA_SOURCES.md](DATA_SOURCES.md); the assistant, its checks and its limits in [ASSISTANT.md](ASSISTANT.md); eligibility and the scheme rules in [ELIGIBILITY.md](ELIGIBILITY.md); voice and languages in [VOICE.md](VOICE.md). This file covers the code.

## Overview

```text
  Browser (React SPA)                           FastAPI service
┌───────────────────────┐   /api/v1/*   ┌─────────────────────────────────┐
│ pages → features →    │ ────────────► │ api/v1       thin routers       │
│ api client            │ ◄──────────── │   └─► services/<pipeline stage> │
└───────────────────────┘     JSON      │ core         config · logging · │
  dev:  Vite proxies /api               │              middleware · errors │
  prod: same origin, or CORS            └───────┬───────────────┬─────────┘
                                                │ reads         │ HTTPS, stateless
   python -m app.cli ingest ──► ChromaDB index + storage/       ▼
   (offline, run by a person)   (verified passages)       Google Gemini API
                                                          (a question and passages only)
```

A single-page app talks to a stateless JSON API. Official documents are collected by a command-line pipeline, not by the API: ingestion is slow, touches the network, and should be run deliberately. The API reads the resulting index to answer questions, and calls a language model to draft the answer; what the model writes is checked against the index before anyone sees it.

## Backend (`backend/app`)

| Layer       | Responsibility                                                                    | Rule                                         |
| ----------- | --------------------------------------------------------------------------------- | -------------------------------------------- |
| `main.py`   | `create_app()`: settings, logging, middleware, error handlers, routers, lifespan | The only place wiring happens                |
| `cli.py`    | Tools (`sources`, `verify`, `ingest`, `search`, `ask`, `assistant-check`, `schemes`, `schemes-check`)         | Thin: parse arguments, call services, print  |
| `api/`      | HTTP concerns: routing, parsing, response models, dependencies                    | Thin: validate, call a service, shape output |
| `services/` | Domain logic, one package per pipeline stage                                      | Never imports from `api/` or `cli`           |
| `domain/`   | Plain data types shared by stages: sources, documents, chunks, reports, answers, errors | No I/O, no logic                       |
| `schemas/`  | Pydantic models for API requests and responses                                    | No logic                                     |
| `core/`     | Settings, logging, middleware, error handling, the rate limiter                   | No domain knowledge                          |

### Pipeline map

The packages under `services/` mirror SPEC section 6. Those marked "built" exist; the rest are still empty.

| Package          | SPEC      | Status  | Holds                                                                   |
| ---------------- | --------- | ------- | ----------------------------------------------------------------------- |
| `ingestion`      | 6.1       | built   | Source registry, fetching, verification, PDF and web-page extraction    |
| `segmentation`   | 6.2       | built   | Text normalisation, structure detection, chunking with page and clause  |
| `retrieval`      | n/a       | built   | Multilingual embeddings, the ChromaDB index, the retriever              |
| `llm`            | n/a       | built   | The `LanguageModel` interface, the Gemini client, every prompt          |
| `grounding`      | 6.6, R1-2 | built   | The check on each claim: exact quote, figures, months, addresses, language |
| `safety`         | 9         | partly  | Built: prompt-injection filter, personal-number removal, abuse refusal. Planned: content filters for uploads |
| `assistant`      | 6.5-6.6   | built   | Question to checked answer: citations, freshness, fixed English and Bengali texts, the source catalog |
| `classification` | 6.3       | planned | Document type                                                           |
| `extraction`     | 6.4       | planned | Structured fields: authority, dates, criteria, deadlines, amounts       |
| `explainer`      | 6.5       | planned | Plain-language explainer of a whole document (the assistant answers questions) |
| `translation`    | 6.7       | planned | Glossary-aware translation of the verified explainer                    |
| `speech`         | 6.8       | planned | Text-to-speech and speech recognition                                   |
| `eligibility`    | 6.9, R3   | built   | Scheme rules as data (TOML), the three-valued rule engine, the checklist, the scheme service |
| `catalogue`      | n/a       | built   | Programmes, services and budget records as checked data (`loader`, `verify`, `budget`) |
| `evaluation`     | n/a       | built   | The benchmark: cases, retrieval and answer metrics, reports (`python -m app.cli eval`) |
| `admin`          | n/a       | built   | Knowledge-base and system health reports behind the admin token |

## The ingestion pipeline

```text
 data/sources/*.toml   curated by a person: URL, issuer, identity phrases, confirmed figures
        │
        ▼
 verify_url ─► Fetcher ─► verify_download ─► extract ─► verify_content ─► chunk ─► embed ─► index
 official       robots.txt   status, redirects,   PDFium or    identity, key facts,   by       e5 via     ChromaDB +
 host?          TLS checked  TLS, file type,      BeautifulSoup date (rule R4),       structure ONNX       audit record
                every hop    size                              scan and OCR flags
        │
        └─ any failed check ► REJECTED: nothing is indexed, and the existing index is untouched
```

**Trust is earned in layers.** A person confirms the URL is the real document when adding it to the registry. The pipeline then re-checks, on every run, that the host is an official one (`*.gov.in`, `*.nic.in` or a listed host), that the certificate chain and hostname verify, that no redirect leaves official domains, that the file really is what was declared, that its text contains the identity phrases the registry lists, and how old it is (SPEC rule R4). Each check ends in `pass`, `warn` or `fail`: one failure rejects the source; warnings keep it but travel with every passage as its `verification` status (`verified` or `verified_with_warnings`), the seed of the SPEC's verification badge.

**Idempotent by fingerprint (SPEC rule R9).** A source's fingerprint hashes the downloaded bytes, the registry entry, the extraction and chunker versions and settings, and the embedding model. If it matches what the index holds, the source is not re-processed, but its checks re-run on the stored text and `verified_at` is refreshed. Any change re-indexes: the new passages are written first and the stale ones deleted after, so a reader never sees an empty source.

**Everything is auditable.** Under `backend/storage/` (git-ignored, safe to delete):

| Path                                   | Holds                                                                      |
| -------------------------------------- | -------------------------------------------------------------------------- |
| `raw/<id>/<sha256 prefix>.<ext>`       | The exact bytes that were downloaded                                       |
| `parsed/<id>.json`                     | Registry entry, fetch details, verification report, extracted text, chunks |
| `chroma/`                              | The vector index                                                           |
| `models/`                              | The embedding model, checked against a pinned SHA-256                      |

**What a passage carries.** Each chunk is stored with its text and flat metadata: `source_id`, `title`, `scheme`, `authority`, `level`, `state`, `doc_type`, `url`, `domain`, `verification`, `verified_at`, `fetched_at`, `document_date` and `date_source`, `page_start`/`page_end` (0 for web pages), `section` (the heading path), `clause` (`2.1`, `(a)`, `Q.7`), `char_start`/`char_end`, `script`, `ocr`, `embedding_model` and the `doc_hash` it came from. A chunk's text is an exact slice of the document's text and its offsets say where, which is what a later "show original" highlight needs.

### Segmentation

PDFs give lines, not paragraphs, so `segmentation/structure.py` infers headings, numbered clauses, FAQ questions and paragraphs from how lines look. The rules were tuned on the four real documents and are conservative: when in doubt, text stays together. The chunker packs blocks to about 900 characters (never above 1,400), starts a new chunk at a heading once the current one has substance, never ends a chunk on an orphaned heading, cuts long blocks at sentence or table-row boundaries (including the Devanagari danda), and repeats a little text when it must continue a long block. Sizes are in characters because token counts differ widely between Latin and Indic text.

### Retrieval

Vectors come from `intfloat/multilingual-e5-small` running locally through ONNX Runtime: no PyTorch, no API key, and no document text leaves the machine. The collection has **no embedding function of its own**; we always compute vectors and hand them to Chroma. A query by text therefore fails loudly rather than silently using another model, and the model's name is recorded in the collection so opening an index built with a different model is refused (`--rebuild` to re-embed). Anonymous telemetry is switched off.

### The assistant

The full account, with the checks, the API and the measurements, is in [ASSISTANT.md](ASSISTANT.md). In short:

```text
question ─► tidy ─► language ─► refuse? ─► remove personal ─► retrieve ─► prompt ─► Gemini ─► check ─► answer
                                (no model)   numbers           top 10      passages   draft     each     citations,
                                                                          cleaned    + quotes  claim    warnings
```

The one rule that shapes the design: **nothing the model writes reaches a user unless code has confirmed it.** The model returns a JSON draft of claims, each with exact quotes; `grounding.verify` looks for every quote in the retrieved passages and for every figure, month and address of the statement in its quotes. What fails is dropped, after one retry in which the model is told which claim and which kind of problem. Everything fixed (refusals, the disclaimer, warnings about sources) is text in `assistant/messages.py`, never model output. `LanguageModel` has one method, so the provider can be swapped or faked; the tests use a scripted model and a mock transport, and `assistant-check` is how an operator proves a real key and model work.

`VectorStore` serves two processes: the API reads for as long as it runs, and `ingest` rewrites. A change leaves a stamp file, a reader reopens the index when it sees a new stamp, and a search that meets an inconsistent index reopens once and retries. Without this, an open reader fails after any re-ingest (measured).

### Conventions

- **Settings.** `core/config.py` uses `pydantic-settings`: typed, validated at start-up, loaded once. To add one, add a field and a documented line to `backend/.env.example`. Tests build their own `Settings`, so a developer's `.env` never leaks into them.
- **One error shape for the API.** Every error is `{"error": {"code", "message", "request_id", "details?"}}`. Raise an `AppError` subclass for a failure the user should understand. Anything unexpected becomes a generic 500 with no internals. Validation errors say *where* a field failed, never the submitted value, because it may be personal data.
- **Ingestion and assistant errors are domain errors.** `domain/errors.py` defines `IngestionError` (and subclasses) and `AssistantError`, each with a stable `code` and a message safe to show. They do not know about HTTP; the API layer maps their codes to statuses (`api/v1/endpoints/assistant.py`) and never shows the operator-facing detail of an index or key problem, which goes to the log instead.
- **An error message never carries text from a question, a passage or a model reply.** Rejection reasons are codes; a malformed model reply is raised without chaining, because the validation error would quote it.
- **Tests are hermetic.** They never read a developer's `backend/.env` (`Settings(_env_file=None)`, or `GEMINI_API_KEY=""` when `get_settings()` is used) and never touch the network: Gemini is faked with a scripted model or a mock transport.
- **Request ids.** `X-Request-ID` is honoured when it is short and harmless, generated otherwise, and attached to every response, error body and log line.
- **Never log document text, questionnaire answers or uploaded content:** log ids and sizes (SPEC AC9). HTTP client loggers are held at WARNING because they log every URL.
- **Middleware is plain ASGI**, not `BaseHTTPMiddleware`, so streaming responses are never buffered.
- **Adding an endpoint.** New module in `api/v1/endpoints/`, include its router in `api/v1/router.py`, models in `schemas/`, logic in `services/`, and a test in `tests/`.
- **Adding a source.** One `[[sources]]` table in `backend/data/sources/`, then `verify`, then `ingest` (see DATA_SOURCES.md).

## Frontend (`frontend/src`)

| Folder        | Holds                                                                                 |
| ------------- | ------------------------------------------------------------------------------------- |
| `app/`        | Providers (TanStack Query, language) and the route table                              |
| `i18n/`       | The language of the interface (provider, hook) and `createTranslator`                 |
| `api/`        | `apiFetch` (timeout, cancellation, one `ApiError` type) and one function per endpoint |
| `features/`   | Vertical slices: the components and hooks of one capability (`health/`, `assistant/`, `schemes/`, `voice/`) |
| `components/` | Shared layout and UI building blocks                                                  |
| `pages/`      | One component per route; they compose features                                        |
| `config/`     | Typed build-time environment access (`env.ts`)                                        |
| `styles/`     | Tailwind entry point and design tokens                                                |
| `test/`       | Test setup and helpers                                                                |

Conventions:

- Import with the `@/` alias for `src/`.
- Server state goes through TanStack Query hooks inside a feature; components never call `fetch` directly.
- Colors come from the tokens in `styles/index.css`, which meet WCAG AA contrast. High-contrast and large-text modes (SPEC feature 13) will be built by re-pointing those tokens.
- Accessibility baseline: skip link, landmarks, one `h1` per page, a live region for async status, touch targets of 48px or more, visible focus, reduced motion respected, and `jsx-a11y` rules enforced by `npm run lint`.
- The whole interface is in three languages (English, Bengali, Hindi). One language (`i18n/LanguageProvider`, switched in the header, remembered in `localStorage`, written to `<html lang>`) drives every screen. Each area has its own table of words, English, Bengali and Hindi, type-checked against each other and tested for equal placeholders and Bengali script (`components/layout/strings.ts`, `features/schemes/strings.ts`, `features/assistant/strings.ts`); `createTranslator` builds the lookup. What a scheme says comes from the API as `{en, bn}` text and is picked with `local()`. Quotes keep the language of their document (`lang="en"`), answers the language they were written in. The answer language of the chat (automatic, English, Bengali) is separate from the language of the interface.
- Anything from the server is shown as text, never as markup, and a link renders only for an `http(s)` address (`OfficialLink`).
- Accessibility is tested three ways: `jsx-a11y` in lint, `axe-core` in the component tests (jsdom cannot compute colour, so contrast is measured and the figures are in the comment at the top of `index.css`), and axe run in a real browser, with contrast, when the page changes.

## Request flows today

**Health.** `StatusPage` (`/status`) renders `HealthStatus`, which calls `useHealth()`, which runs `fetchHealth()`, which calls `apiFetch('/api/v1/health')`. In development the Vite proxy forwards `/api` to `API_PROXY_TARGET`. In production the API is served from the same origin, or from `VITE_API_BASE_URL` with that origin listed in `CORS_ORIGINS`. FastAPI: request-id middleware, then the router, then `get_health`. A failure at any step becomes an `ApiError`, which the card shows in plain language along with the reference id.

**Asking.** `ChatPage` holds the answer-language choice (remembered in `localStorage`, with the interface language the only things stored), the conversation in `useChat()` (in memory, one question at a time, cancelled when the page is left) and the optional scheme (`?scheme=`, which becomes `source_ids`), and lists the sources with `useSources()`. `AskForm` submits `POST /api/v1/assistant/ask`; the rate limiter runs first, then `get_assistant_runtime` builds the assistant on first use, then the endpoint (a plain `def`, so FastAPI runs it in a worker thread while it waits on the embedder and Gemini) calls `AssistantService.ask`. `ChatTurn` shows the question and then the wait, the failure or the `AnswerView`, which shows the claims, each with buttons that open the quote it rests on, the warnings, and the sources; a new answer takes keyboard focus. An `AssistantError` becomes a coded error response and an `AskError` with a reference id and a retry.

**Talking.** `VoiceConversation` (on `ChatPage`) speaks a prompt, starts `useDictation` in the spoken language, and when listening ends with words calls `useChat().ask()`, which resolves with the outcome; the answer is read with `speaker.speak(..., onEnd)` and `onEnd` starts the next listening. A session counter makes every late callback harmless after Stop. The conversation is the page's own `chat.turns`, so it is rendered, retried and cleared like typed questions.

**Listening and speaking.** `ListenControl` (in `AnswerView`, `ResultView`, `SchemeDetailsView`) builds its text with `speechText.ts` and asks the one `speaker` to read it: it finds a voice for the language (`pickVoice`), cuts the text into sentences and speaks them in turn; with no voice it renders a note instead of a button. `MicButton` (in `AskForm`) starts a `SpeechRecognition` session in the language chosen, passes the growing transcript to the question box, and returns focus to it when the session ends. No request is made to the server for either.

**Checking eligibility.** `EligibilityPage` reads the scheme with `useScheme()` and the course from `?track=`, and keeps the answers as text in memory (never in the address or storage). `EligibilityForm` turns them into `{field: value}`, leaving skipped questions out and reporting unusable numbers (`answers.ts`; Bengali digits are read as 0-9), and `useEligibilityCheck()` posts to `/api/v1/schemes/{id}/eligibility`. The router calls `get_scheme_service` (rules loaded and checked on first use), then `SchemeService.check`, which validates the answers against the track's questions and calls the pure `evaluate`. `ResultView` shows the outcome in words and a mark, each rule with the quote behind it, what is still needed, and the checklist; any change to an answer clears the result so it never disagrees with the form.

## Decisions

| Decision                                         | Why                                                                                                                                                              | Revisit when                                                  |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Curated registry plus automated verification     | Anyone can publish a "scheme guideline"; a person vouches for each URL once, and the machine re-checks it on every run (SPEC section 9, misinformation guard).   | Users can submit their own URLs: add an "unverified" tier     |
| PDFium (`pypdfium2`) for PDFs                    | Decodes symbol fonts, bullets and dashes that pure-Python libraries turned into `U+FFFD`; copes with malformed files; renders pages, which OCR will need.         | A document needs table extraction                             |
| Detect scans by invisible text (render mode 3)   | A scan with an OCR layer has *all* text invisible; native PDFs have none. Image coverage alone misfires (a background image covers half of a native page).        | Never needed unless a scanner writes visible text             |
| Chroma with explicit embeddings, no function     | One embedder for documents and queries, by construction. Chroma's default would silently embed with an English-only model, and e5-small shares its 384 dimensions. | Hosted vector search                                          |
| `multilingual-e5-small` through ONNX Runtime     | Covers Hindi, Bengali, Tamil and the rest of SPEC section 4, so a Bengali question can find an English passage. About 490 MB, CPU only, no PyTorch.              | Retrieval quality on real questions is measured and found low |
| Pinned model revision and SHA-256                | A 490 MB binary is downloaded and executed; an upstream change must not silently change vectors.                                                                 | The default model changes                                     |
| `httpx2` with the OS trust store (`truststore`)  | Starlette itself now prefers `httpx2`. The OS store also handles government sites that omit intermediate certificates.                                            | n/a                                                           |
| Per-source `legacy_tls`                          | `svmcm.wb.gov.in` only supports legacy TLS renegotiation, which OpenSSL 3 refuses. An explicit, documented, per-source switch keeps the exception visible; the certificate and hostname are still verified, and every report warns about it. | The site is fixed                                             |
| Certificate revocation is not checked            | Python's TLS stack does not (neither do `requests` or `httpx`), and OCSP support is a large addition. The reports say so. NSP is excluded by hand for this reason.  | A source needs it, or `cryptography` is already a dependency  |
| Chunk sizes in characters                        | Token counts for Hindi or Bengali are two to three times those for English text of the same length; characters are a safe common unit.                            | A token-aware chunker is worth its coupling to the embedder   |
| Gemini through `google-genai`, stateless `generate_content`, JSON schema | One call in, one typed draft out; no conversation, nothing stored on Google's side, and the schema keeps the reply parseable. Tests inject a mock transport, so the whole error mapping is covered with no key. | The Interactions API or another provider is needed: implement `LanguageModel` |
| Deterministic grounding, not a second model call | Exact-quote and figure checks are testable, free and fast; a judge model would double the cost and could not be tested without a key. It cannot judge *meaning* (see ASSISTANT.md). | Meaning errors are found in evaluation: add a model pass behind a setting |
| Quotes are matched on letters, vowel signs and digits only | A model that re-types a quote changes white space, punctuation, quotes and the script of digits, not the words; matching on that is robust and a different word still fails. | n/a |
| Dense retrieval only, top 10, a low floor        | Keyword fusion measured worse (Hindi and Bengali questions, English documents); a rewrite step cost a call for a small gain; e5 scores are too squeezed to threshold on answerability. | The corpus grows past what top 10 can cover: re-measure       |
| Fixed texts for refusals, disclaimer and warnings | The legal disclaimer (R6) and every warning must read exactly as written, whatever the question or the model does. | n/a                                                           |
| Passages cleaned and tagged with a random code before the model | An instruction in a document must never reach the model as an instruction, and no text can close its own tag.                                       | A source that legitimately addresses an AI                    |
| Stamp file plus reopen for the vector index      | Measured: an API that keeps the index open fails after `ingest` rewrites it. A stamp lets it follow without a restart; a retry covers a write that lands mid-query. | A server-mode vector database replaces embedded Chroma        |
| In-memory rate limiter                           | Each question costs a paid, rate-limited call; per client address over a sliding minute stops a runaway script. It is per process, so a shared hard limit belongs at the proxy. | More than one API process behind a public address             |
| The assistant is imported and built on first use | A missing index or key, or a broken install of ChromaDB, ONNX Runtime or the Gemini SDK, must never stop `/health` from answering; a failed build is retried on the next request. It also takes server start-up from about 3 s to 1 s, which every `--reload` feels. A test keeps those libraries off the start-up path. | n/a                                                           |
| Oxlint instead of ESLint                         | It is the Vite template's default and has built-in React and a11y rules. `typescript-eslint` 8.72 declares support only for TypeScript below 6.1, so the ESLint variant does not install next to TypeScript 7. | `typescript-eslint` supports TypeScript 7                     |
| Tailwind v4 with design tokens, TanStack Query   | Fast to build many screens with one place to change colors; caching, cancellation and retries for server state.                                                  | n/a                                                           |
| Hand-written API types                           | Few endpoints today, and `src/api/types.ts` names the backend model each one mirrors.                                                                            | The surface grows: generate from `/api/v1/openapi.json`      |
| No PWA or OCR yet; a small hand-made translator, no i18n library | Two languages and a few hundred strings: a typed table per area and a 15-line `createTranslator` are enough, and the type checker finds a missing entry. | A third language, or plurals and gender that need real message formatting |
| Scheme rules are TOML data, checked at load      | A rule is read by people against the official document, edited without touching code, and every figure and quote can be proven (`schemes-check`). | Rules too varied for `field op value` conditions               |
| Voice runs in the browser: `speechSynthesis` and `SpeechRecognition`, nothing on the server | No key, no bill, no new dependency, and the audio of a spoken question never reaches CivicSaathi (the browser maker's service gets it, and the page says so). The cost: voices depend on the device, so a text is read only with a voice for its language, else the page says so. | A guaranteed voice everywhere, downloadable audio (SPEC feature 5) or offline use: a server-side TTS |
| Hindi as a full third language, not a translation layer | Answers, fixed texts, scheme rules and screens each carry `hi`; a scheme file without it does not load, and the same quote check covers its figures. Adding a language is a table per area plus the backend script check, not a flag. | A fourth language: budget a native-speaker review for every table |
| Three-valued rules (true, false, unknown)        | A skipped question must never become "eligible" (AC6); a definite failure is final, an unknown is asked for. | n/a                                                           |
| Direct dependency pins plus `constraints.txt`    | Repeatable installs, and about 5 minutes instead of 15 or more in pip's resolver; the frontend is pinned by `package-lock.json`.                                 | Switching to a real lock-file tool                            |

## Known limitations

- **Scans.** Text from a scan comes from its embedded OCR layer, which can misread digits and letters: the AICTE notification's "15 November" is read as `1 5"' Novcmber`. Such passages carry `ocr = true` and the report warns; figures in them must be checked against the original. Scans without any text layer are rejected until OCR is added.
- **Tables in PDFs** are flattened and their columns can interleave. The same table on a web page is extracted properly, with each row labelled by its column headers, so prefer the web version when both exist.
- **Garbled text from legacy-font OCR** (an English OCR engine reading a Hindi letterhead) is not filtered; it is flagged only through `ocr`.
- **Web pages without a date** get an "effective date unknown" warning; extracting dates from the text itself belongs to the structured-extraction stage (SPEC 6.4).
- **One language per run of text.** Scripts are detected per passage, but mixed-language documents are not yet split by language (SPEC section 8).
- **The assistant checks quotes and figures, not meaning.** A statement whose figures are right and whose meaning is reversed passes; the quote under every claim is the safeguard. See ASSISTANT.md for this and the other limits.
- **Gemini has not been called by the author.** There was no key, so the client is tested through a mock transport and the live behaviour (model name, JSON adherence, exact quotes, Bengali) is unverified until `assistant-check` is run with a key.
- **The Bengali is a draft.** Interface and fixed texts were written by a non-native speaker and need a native reviewer.
