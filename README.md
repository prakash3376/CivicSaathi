# CivicSaathi

Paste, upload or link a government notification, scheme guideline or municipal rule, and get a plain-language explainer in your own language, as text or audio: what it says, whether you qualify, what to do, and by when.

- Product spec: [SPEC.md](SPEC.md)
- How the code is organised, and why: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Which official sources are ingested, and how they were verified: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)
- How the assistant answers, what its checks guarantee and what they do not: [docs/ASSISTANT.md](docs/ASSISTANT.md)
- How eligibility is decided, and how a scheme is written as data: [docs/ELIGIBILITY.md](docs/ELIGIBILITY.md)
- Voice (listen, speak a question) and the three languages: [docs/VOICE.md](docs/VOICE.md)

**Status: Phases 4 and 5, eligibility and the product screens.** You can browse the scholarship schemes, read what each requires with the official words behind every rule, answer a few questions and get one of three results (eligible, not eligible, need more info) with a document checklist, all in English, Hindi or Bengali, and you can listen to answers and results or speak a question. The result comes from fixed rules, not a language model, and a skipped question never gives "eligible" (details: [docs/ELIGIBILITY.md](docs/ELIGIBILITY.md)). You can also chat with the assistant, optionally about one scheme. The assistant (Phase 3): you can ask questions about the indexed scholarships in English or Bengali. Every statement in an answer comes with a quote from an official document, checked word for word and figure for figure by code, with the quote highlighted in its source; sources are dated and flagged when old or scanned; instructions hidden in a document are not followed. Uploading your own documents, explainers and audio arrive in later phases.

## Prerequisites

| Tool    | Version                           | Check with         |
| ------- | --------------------------------- | ------------------ |
| Python  | 3.11 or newer (developed on 3.13) | `python --version` |
| Node.js | 22.22 or newer (developed on 24)  | `node --version`   |

## Run it locally

You need two terminals, one per half.

### Terminal 1: backend (FastAPI)

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints.txt
Copy-Item .env.example .env        # optional: the defaults already work
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

macOS / Linux:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt -c constraints.txt
cp .env.example .env               # optional: the defaults already work
.venv/bin/python -m uvicorn app.main:app --reload
```

The install takes a few minutes: ChromaDB has a large dependency tree, and `constraints.txt` pins every version so pip does not have to search for a compatible set.

The API listens on <http://127.0.0.1:8000>. Try the [health check](http://127.0.0.1:8000/api/v1/health) and the interactive docs at [/docs](http://127.0.0.1:8000/docs).

### Terminal 2: frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The **System status** card should read **Connected**. That is the browser reaching the backend through the dev server's `/api` proxy.

## Collect and index the official sources

The ingestion tools run from `backend/` and need no server. Use the venv's Python as above (shown for Windows; on macOS and Linux use `.venv/bin/python`).

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli sources     # what is registered, and how much is indexed
.\.venv\Scripts\python.exe -m app.cli verify      # download and check every source; indexes nothing
.\.venv\Scripts\python.exe -m app.cli ingest      # verify, read, chunk, embed and index
.\.venv\Scripts\python.exe -m app.cli search "What is the family income limit?"
.\.venv\Scripts\python.exe -m app.cli search "छात्रवृत्ति के लिए पारिवारिक आय की सीमा क्या है?"
```

- **The first `ingest` downloads the embedding model, about 490 MB, once.** It is kept in `backend/storage/models/` and checked against a pinned checksum. After that, everything except the document downloads works offline.
- **Re-running is safe and cheap.** A source whose document, registry entry and settings are unchanged is not re-processed, but it is re-verified so "last verified" stays current. `--force` re-processes anyway; `--rebuild` empties the index first (needed after changing `EMBEDDING_MODEL`).
- **A source that fails verification never touches the index.** What was indexed before stays exactly as it was.
- You can ask in English, Hindi or Bengali: the model matches meaning across languages.

The registered sources live in [backend/data/sources/scholarships.toml](backend/data/sources/scholarships.toml); [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) explains how to add one.

## Ask questions (the assistant)

Open <http://localhost:5173/ask> once the sources are indexed. The assistant needs a Google Gemini API key; without one the page loads, lists the documents, and asking says the assistant is not set up (everything else keeps working).

1. Get a key at <https://aistudio.google.com/apikey> and put it in `backend/.env`: `GEMINI_API_KEY=...` (see [backend/.env.example](backend/.env.example)). Never commit it; restart the backend after changing it.
2. Check the setup. This is the only way to know that the key, the model name and Gemini's behaviour (JSON, exact quotes, Bengali) all work on your machine:

   ```powershell
   .\.venv\Scripts\python.exe -m app.cli assistant-check
   ```

3. Try it from the terminal, or in the browser:

   ```powershell
   .\.venv\Scripts\python.exe -m app.cli ask "What is the maximum family income to get the SVMCM scholarship?"
   .\.venv\Scripts\python.exe -m app.cli ask "SVMCM বৃত্তি পেতে পরিবারের সর্বোচ্চ আয় কত হতে হবে?" --language bn
   ```

**Privacy.** Each question (with personal numbers such as Aadhaar, PAN, phone and bank numbers removed first) and the passages sent with it go to Google. On the free tier of the Gemini API Google may use that data to improve its products; the paid tier does not. **Use a paid key before real people use this.** Nothing is logged but counts and codes, and the browser remembers only the chosen language.

`GEMINI_MODEL` defaults to `gemini-3.6-flash`, which the author could not test without a key: if `assistant-check` says the model is refused, set another model your key can use. You can re-run `ingest` while the API is running; it picks up the new index by itself.

## Schemes and eligibility

Open <http://localhost:5173/schemes>. This part needs only the backend: no Gemini key and no index (the "official words" links name the documents when the index exists). Two commands help whoever edits the rules in `backend/data/schemes/`:

```powershell
.\.venv\Scripts\python.exe -m app.cli schemes         # load and list the schemes and their rules
.\.venv\Scripts\python.exe -m app.cli schemes-check   # every quote must still be in its indexed document
```

The answers to the questionnaire are used for one response and never stored or logged. The screens: `/schemes` (catalogue), `/schemes/:id` (details by course), `/schemes/:id/check` (questions, result, checklist), `/ask` (chat; `?scheme=svmcm` limits it to one scheme) and `/status` (is the API up). The English / বাংলা / हिन्दी switch in the header changes the whole interface and is remembered.

## Voice and languages

On `/ask`, press **Start talking** to have a spoken conversation: it listens, answers aloud in English, Hindi or Bengali, and listens again. Open any answer, result or scheme page and press **Listen**; on `/ask` press the microphone to speak a question. It uses your browser's own speech, so it needs a browser with a Hindi or Bengali voice for those languages (Chrome and Edge usually have them; Windows may need a speech language pack) and an internet connection for the microphone: **the recording goes to the browser maker's speech service, never to CivicSaathi**. Without a voice the page says so and shows the text. Details and limits: [docs/VOICE.md](docs/VOICE.md).

The assistant answers in English, Hindi or Bengali: `python -m app.cli ask "..." --language hi`, and `assistant-check` tests all three with your key.

## Everyday commands

Backend commands run from `backend/` with the virtual environment active, or prefixed with the venv's Python as above. Frontend commands run from `frontend/`.

| Task             | Backend                   | Frontend            |
| ---------------- | ------------------------- | ------------------- |
| Tests            | `python -m pytest`        | `npm test`          |
| Lint             | `python -m ruff check .`  | `npm run lint`      |
| Format           | `python -m ruff format .` | `npm run format`    |
| Type-check       | `python -m mypy`          | `npm run typecheck` |
| Production build | n/a                       | `npm run build`     |

`python -m pytest -m live` also runs the tests that need the internet, the real embedding model or a Gemini key: they check that the registered sources still verify against the live websites, that Hindi and Bengali questions find the right English passage, and (with a key) that Gemini answers in both languages with verifiable quotes. They are skipped by default, and the Gemini ones skip without `GEMINI_API_KEY`.

## Configuration

Both halves run with no configuration. To change something, copy the `.env.example` beside each app and edit the copy. Real environment variables always win over files. Real `.env` files are git-ignored: never commit secrets.

**Backend** (`backend/.env`)

| Variable                | Default                                       | Meaning                                                                                  |
| ----------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `APP_ENV`               | `development`                                 | `development`, `test`, `staging` or `production`. `/docs` is switched off in production. |
| `LOG_LEVEL`             | `INFO`                                        | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`.                                       |
| `CORS_ORIGINS`          | `http://localhost:5173,http://127.0.0.1:5173` | Browser origins allowed to call the API directly. `*` is rejected in production.         |
| `DATA_DIR`              | `storage`                                     | Downloads, the vector index and the model. Relative to `backend/`. Safe to delete.       |
| `EMBEDDING_MODEL`       | `intfloat/multilingual-e5-small`              | Model for embeddings. Changing it needs `ingest --rebuild`.                              |
| `FETCH_TIMEOUT_SECONDS` | `30`                                          | Give up on a document download after this long.                                          |
| `MAX_DOCUMENT_MB`       | `25`                                          | Refuse documents larger than this (the SPEC limit).                                      |

The assistant's settings (all optional except the key; defaults and notes are in `backend/.env.example`):

| Variable                          | Default            | Meaning                                                                       |
| --------------------------------- | ------------------ | ----------------------------------------------------------------------------- |
| `GEMINI_API_KEY`                  | empty              | Without it the assistant is off. Put it only in your own `.env`.              |
| `GEMINI_MODEL`                    | `gemini-3.6-flash` | The model to ask. Use one your key can access.                                |
| `GEMINI_BASE_URL`                 | empty              | A gateway, regional endpoint or test double instead of Google's address.      |
| `GEMINI_TIMEOUT_SECONDS`          | `45`               | Give up on the model after this long.                                         |
| `GEMINI_MAX_OUTPUT_TOKENS`        | `4096`             | Cap on one reply.                                                             |
| `GEMINI_THINKING_LEVEL`           | empty              | `minimal`, `low`, `medium` or `high`; lower is faster and cheaper.            |
| `ASSISTANT_MAX_QUESTION_CHARS`    | `500`              | Longer questions are refused.                                                 |
| `ASSISTANT_RATE_LIMIT_PER_MINUTE` | `20`               | Questions one client address may ask per minute; `0` switches the limit off.  |

**Frontend** (`frontend/.env.local`)

| Variable            | Default                 | Meaning                                                                                             |
| ------------------- | ----------------------- | --------------------------------------------------------------------------------------------------- |
| `VITE_API_BASE_URL` | empty                   | API origin as the browser sees it. Leave empty to use the same origin (dev proxy or reverse proxy). |
| `API_PROXY_TARGET`  | `http://127.0.0.1:8000` | Where the dev server forwards `/api`. Development only; never sent to the browser.                  |

## Project layout

```text
CivicSaathi/
├── SPEC.md                  Product spec
├── docs/                    Architecture, and the verified data sources
├── backend/                 FastAPI service
│   ├── app/
│   │   ├── main.py          App factory and ASGI entry point
│   │   ├── cli.py           Ingestion tools: python -m app.cli ...
│   │   ├── core/            Settings, logging, middleware, error handling
│   │   ├── api/v1/          Thin routers, served under /api/v1
│   │   ├── schemas/         Pydantic request and response models
│   │   ├── domain/          Plain data types shared by the pipeline stages
│   │   └── services/        One package per pipeline stage (SPEC section 6)
│   │       ├── ingestion/     registry, fetching, verification, PDF and web extraction
│   │       ├── segmentation/  structure detection and chunking
│   │       ├── retrieval/     embeddings, the ChromaDB index, the retriever
│   │       ├── safety/        prompt-injection filter, personal-number removal, abuse refusal
│   │       ├── grounding/     the check: exact quotes, figures, months, addresses, language
│   │       ├── llm/           the Gemini client and every prompt
│   │       ├── assistant/     the question-to-answer flow, citations, freshness, fixed texts
│   │       └── eligibility/   scheme rules as data, the rule engine, the checklist
│   ├── data/sources/        The curated registry of official sources (TOML)
│   ├── data/schemes/        Scholarship rules as data (TOML), in three languages, with the official quote behind each
│   ├── storage/             Downloads, index and model (git-ignored, created on first use)
│   └── tests/
└── frontend/                React + Vite + TypeScript
    └── src/
        ├── app/             Providers and the route table
        ├── api/             HTTP client and one function per endpoint
        ├── features/        Feature slices (assistant, schemes, voice, health): components and hooks together
        ├── i18n/            Language of the interface (English / Bengali / Hindi) and the translator
        ├── components/      Shared layout and UI
        ├── pages/           One component per route
        └── config/ styles/ test/
```

## Troubleshooting

- **The status card says "Server unavailable".** Start the backend. If it runs on another port, set `API_PROXY_TARGET` in `frontend/.env.local` and restart `npm run dev`.
- **VS Code underlines Python imports.** Run _Python: Select Interpreter_ and choose `backend/.venv`.
- **PowerShell refuses to run `Activate.ps1`.** You do not need it: the commands above call the venv's Python directly.
- **Testing on a phone.** Run `npm run dev -- --host`, then open `http://<your-computer-ip>:5173` on the same Wi-Fi. The proxy still reaches the backend, which can stay on localhost.
- **`ingest` cannot download the model.** Check your internet connection and run it again; the download resumes. The files are verified against a pinned checksum, so a damaged download is deleted rather than used.
- **A source is `REJECTED`.** `python -m app.cli verify <id>` prints every check. A failing TLS check means the site's certificate could not be verified: do not work around it, report it to the site owner. A failing identity check means the document at that address is not the one the registry describes.
- **Asking says "The assistant is not set up".** There is no `GEMINI_API_KEY` in `backend/.env`, or the backend was not restarted after you added it. `python -m app.cli assistant-check` says exactly what is missing.
- **Asking says "not available right now" (503).** The backend log says why in one line: `Gemini refused the API key` (check the key), `Gemini rejected the request ... check GEMINI_MODEL` (the model name is wrong for your key), or `Gemini is unavailable`. The user is deliberately told only the neutral message.
- **"The library of official documents is empty".** Run `python -m app.cli ingest`.
- **Every answer says the documents do not say it.** Run `assistant-check`: if the English and Bengali probes fail with `number` or `quote_not_found`, the model is not copying quotes exactly and may need a stronger model.
- **Hindi or Bengali text shows as `?` in the terminal.** The tools force UTF-8, but an old console font may lack the glyphs. Windows Terminal or VS Code's terminal show them correctly.
