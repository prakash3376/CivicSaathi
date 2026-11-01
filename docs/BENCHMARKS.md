# Benchmarks: what was measured, how, and what it does not show

Every figure here came from a script in this repository, run on the machine below, against the real data and the real index. Nothing is mocked. Raw reports are written to `backend/storage/benchmarks/` and `backend/storage/eval/` (derived data; safe to delete, and re-run to get your own numbers). A figure that was **not** measured is said to be unmeasured, not estimated.

**Machine:** Windows 11, 22 logical CPUs, Python 3.13.14, Chrome for the browser checks. The client and the server shared that machine, over the loopback network. These are figures for this process on this machine, not a promise about a deployment.

## 1. Public API: before and after the performance work

`python scripts/benchmark_api.py` starts the real server twice on local ports. **Before** = `CACHE_ENABLED=false COMPRESS_RESPONSES=false ACCESS_LOG=false`. **After** = the defaults. Each endpoint: 3 warm-up calls, then 100 sequential requests, 100 repeat requests that send back the ETag (as a browser does), and 100 requests from 8 clients at once. The client accepts gzip in both variants. The assistant is not asked (a model call costs quota and measures Google).

Run `api-20261101-074521` (both variants in one run, so the data is identical):

| Endpoint | p50 ms (before → after) | Bytes on the wire (before → after) | Revalidation p50 ms (before → after) | 8 clients, p95 ms (before → after) |
| --- | --- | --- | --- | --- |
| `/health` | 2.7 → 3.0 | 152 → 152 | 2.7 → 3.1 (always a full 200) | 29.2 → 26.9 |
| `/schemes` | 5.6 → 21.7 | 147,368 → 33,811 (**-77%**) | 4.9 → 6.0 (304) | 44.2 → 57.5 |
| `/schemes/pm-kisan` | 4.0 → 5.1 | 5,940 → 2,138 (**-64%**) | 3.9 → 5.2 (304) | 33.6 → 34.4 |
| `/budget` | 5.0 → 13.1 | 143,653 → 21,158 (**-85%**) | 5.7 → 6.2 (304) | 41.7 → 306.3 (see below) |
| `/sources` | 1,559 → 20.8 | 71,648 → 10,279 (**-86%**) | 3,722 → 20.5 (304) | 25,989 → 180.3 |

Zero errors in every cell.

**What this says**

- The real win is `/sources`. It listed every indexed document by scanning the whole vector index on each request: 1.6 s typical, 3.8 s at the 95th percentile, and **26 s at the 95th percentile with 8 clients at once** (they queue behind one another). It now reads a metadata scan cached against the index's change stamp (a new stamp, from `ingest`, drops it): 21 ms, and 180 ms under 8 clients.
- Compression cuts the bytes of every large reply by 64-86%, which is what a visitor on a slow mobile connection waits for. **It costs CPU**: `/schemes` and `/budget` are *slower* to answer on a loopback connection (where bytes are free) because gzip takes time. That trade is right for a phone and wrong for a benchmark on localhost, so the table shows it rather than hiding it. Level 9 was measured too and was slower still; level 5 is the setting.
- Small replies (under 1 KB) are not compressed and did not change. `/health` and `/schemes/pm-kisan` are within noise.
- The "before" variant **already had** ETag revalidation (a middleware that predates this work), so its repeat requests were already 304s with zero bytes. The 304s are therefore not an improvement claimed here. `/sources` revalidation is the exception: it still had to scan the index to compute the tag (3.7 s) and now does not.
- `/budget` at 8 clients (p95 306 ms) was a single-run outlier: the second run below, same code, shows 45 ms. Treat one-off p95 values on this machine as having a floor of tens of milliseconds from the client itself (a new connection per request in `urllib`).

Run `api-20261101-074646` (after only, a later run; the served data was not byte-identical to the first run, so compare sizes only within a run):

| Endpoint | p50 ms | Bytes | Revalidation p50 ms | 8 clients p95 ms |
| --- | --- | --- | --- | --- |
| `/health` | 3.4 | 152 | 2.8 | 25.1 |
| `/schemes` | 11.1 | 35,594 | 4.7 | 46.9 |
| `/schemes/pm-kisan` | 4.1 | 2,146 | 4.0 | 29.1 |
| `/budget` | 10.1 | 21,638 | 5.6 | 45.1 |
| `/sources` | 23.2 | 10,731 | 21.9 | 166.9 |

The same `/schemes` p50 was 21.7 ms in one run and 11.1 ms in the other: run-to-run variation on this machine is as large as some of the differences in the first table, so only the order-of-magnitude changes (`/sources`, bytes) are claims.

## 2. Load test

`python scripts/loadtest.py --users 20 --seconds 20`: 20 simulated visitors, each looping through the schemes list, sources, budget, one programme and one eligibility check with 0.2-0.6 s pauses, replaying the ETags they were given. Run `load-20261101-074720`:

| | |
| --- | --- |
| Requests | 2,894 in 20.5 s (141 per second) |
| Errors | **0** |
| Answered by 304 (revalidation) | 2,236 of the 2,316 list and detail GETs (97%) |
| p50 / p95 / p99 per endpoint | 42-67 / 114-172 / 163-275 ms (the slowest is `/sources`: 67 / 172 / 275 ms; the eligibility `POST`: 42 / 116 / 163 ms) |

Limits: the load generator ran on the same machine as the server; **server memory was not measured** (`psutil` is not installed, so the report says `null`); there is **no "before" load test**, so no improvement is claimed from it; the assistant endpoint was not loaded.

## 3. Frontend bundle

`npm run build` (Vite 8). Routes load their code on demand; the entry and shared chunks are preloaded by `index.html`.

| | Raw | gzip |
| --- | --- | --- |
| All JavaScript, every chunk (what a single bundle would contain) | 586 kB | 184 kB |
| What `/` downloads: entry + the 11 preloaded shared chunks | 500 kB | 156 kB |
| Saved on the first page by lazy routes | 86 kB (15%) | 28 kB (15%) |
| Pages loaded only when visited | Chat 21 kB, Eligibility 13 kB, Sector 12 kB, Admin 7 kB, Scheme details 8 kB, others 1-4 kB | |

This is a **modest** saving, not a dramatic one: the shared chunks (the query client, the three-language text tables, the scheme and sector text) are needed by the home page too. A "before" build was not made; the single-bundle row is the sum of all chunks. CSS is 22 kB (5 kB gzip). These were re-measured after the reliability work, which added the error pages and the offline notice to the first download (the entry chunk grew from 270.5 kB to 276.5 kB; 84.7 kB gzip).

## 4. Retrieval quality (211 questions, no model involved)

`python -m app.cli eval --strategy dense|knowledge [--features ...]`. The set (`backend/data/eval/questions.toml`, run by `app/services/evaluation`) is 211 questions: 63 handwritten (including English/Hindi/Bengali pairs of the same question, follow-ups that need the previous turn, colloquial wording, cross-sector questions) and 148 derived from the verified quotes of the records. For each question the gold is the document(s), and for derived cases the passage, that should be found.

- **source recall@5**: the expected document is among the top 5 passages.
- **evidence hit@5**: the passage holding the expected quote is among the top 5 (stricter).
- **MRR**: mean reciprocal rank of the first expected document.

Ablation, one run per row, default sector hint = none (the question carries no page context). Re-run on 1 Nov 2026 with each feature set recorded:

| Configuration | Source recall@5 | Evidence hit@5 | MRR | Bengali recall (13 cases) | Hindi recall (13 cases) | Mean ms |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline: dense search only (before) | 0.886 | 0.536 | 0.830 | 0.538 | 0.923 | 29 |
| Router only | 0.962 | 0.616 | 0.937 | 0.846 | 1.000 | 74 |
| History only | 0.900 | 0.550 | 0.844 | 0.538 | 0.923 | 33 |
| **Default**: history + router + sector | **0.981** | **0.630** | **0.956** | **0.846** | **1.000** | 73 |
| Default + keywords (BM25) | 0.981 | 0.592 | 0.962 | 0.846 | 1.000 | 86 |
| Default + per-document cap | 0.981 | 0.607 | 0.956 | 0.846 | 1.000 | 74 |
| All five features | 0.981 | 0.569 | 0.962 | 0.846 | 1.000 | 103 |

The "sector" feature does nothing in this table because no sector is given; it is measured below. The default was chosen by this table: the router is the large gain, history fixes follow-ups, and keywords and the cap each *lowered* evidence hit rate, so they stay off.

With the sector the visitor is browsing (the front end sends it) the same default gives:

| `--hint` | Source recall@5 | Evidence hit@5 | MRR |
| --- | --- | --- | --- |
| none (no page context) | 0.981 | 0.630 | 0.956 |
| right (the question's own sector) | 0.986 | 0.649 | 0.976 |
| wrong (another sector's page) | 0.967 | 0.607 | 0.945 |

A wrong hint costs 1.4 points of recall; it is a soft nudge, never a filter, so a question asked on the wrong page can still find its answer.

**Per question type (default, hint right)**: factual 74 questions, recall 1.00; eligibility 67, 1.00; numeric 20, 1.00; multilingual 38, 0.97; colloquial 5, 1.00; follow-up 4, 1.00; **cross-sector 3, 0.33**. By sector, evidence hit ranges from 0.29 (employment: 17 questions) to 0.90 (environment). Latency of retrieval alone: mean 73 ms, p95 102 ms (the router costs about 45 ms over dense search).

**Intent classification** (rule-based, English/Hindi/Bengali): 0.835 on 218 labelled questions. Part of the gap is label ambiguity (a question such as "farmer money" is both scheme discovery and eligibility), and the rules were written by the same people who wrote the questions, so this is not a held-out estimate. It decides routing, not the wording of an answer.

### What the retrieval numbers do not show

- **The gold was widened once** during development (the set of documents accepted as correct for some questions). The before and after rows above use the same final set, so the comparison is like for like, but the absolute numbers are not those of a set fixed in advance, and figures quoted from earlier runs may differ from these.
- **Bengali and Hindi have 13 questions each.** 0.846 is 11 of 13; one question moves it by 8 points. Bengali is the weakest language and the embedding model (multilingual-e5-small) is the likely cause. It is a direction, not a precise figure.
- **Evidence hit@5 is 0.63.** In about a third of questions the exact passage with the quote is not in the top 5 even when the right document is. Fewer misses here would need a stronger embedding model or passage re-ranking; neither was done.
- **Derived questions are easy by construction** (they are phrased from the quote they test), so they push source recall up; the handwritten 63 are the honest subset: source recall 0.952, evidence hit 0.651, MRR 0.928 with the right hint.
- Cross-sector questions are 3 cases; the 0.33 is a known weakness, not a statistic.

## 5. Live answers (needs a Gemini key and network)

`python -m app.cli eval --strategy knowledge --answer --limit N` asks the real model for the first N answerable questions, then checks the reply through the same grounding checks a visitor would be protected by. **Correct** = the answer was accepted and cited the expected document. Run `20261101-075121`, 16 questions (English, Hindi and Bengali pairs; agriculture, health, women and child):

| | |
| --- | --- |
| Correct | **12 of 16 (0.75)** |
| Reply in the question's language | 16 of 16 |
| Errors (exceptions) | 0 |
| Latency of a full answer | mean 11.1 s, p95 15.7 s (the model call dominates) |

The four misses: the Bengali "PM-KISAN amount" and "crop insurance" questions (the cited document was not the expected one; the Bengali retrieval weakness above is the likely cause, not a proven one), and "health insurance in West Bengal" in English and Hindi (answered, but from a different document than the one named in the gold).

I re-ran those four on their own (`...075326`): **0 of 4**, now with different reasons (three where the model declined to answer, one wrong source again). The answers are therefore **not stable run to run** on these questions: a model call is not deterministic, and 16 questions is too few to put a confidence interval on. What these runs support: the reply was in the right language every time (16 of 16), Bengali missed 2 of its 4 questions against 2 of the other 12 (too few to call a difference, but it agrees with the retrieval table), and no stronger claim about answer accuracy has been measured. That unverified model text is never shown is enforced by the grounding code and its tests; this benchmark does not test it.

No "before" live run exists, so there is no comparison to the old assistant. Abstention on unanswerable questions was **not** measured here (the set has none in this run's slice).

## 6. End-to-end and accessibility, in real Chrome

- `frontend/e2e/journey.mjs`: ten steps through the running app, with an axe accessibility check on each page, and a final check that the console is free of script errors: home, a sector, search in the sector, a scheme's details, eligibility with every question skipped (it must never say "eligible"), the assistant with the model made to fail (the matching official passages and a "Try again" button must appear), the sources of that reply, another sector (budget), switching to Hindi, and recovering by asking again. Result: **11 of 11 passed**, no axe violations.
- A wider sweep (a script in the working folder, not committed) opened 19 pages (home, schemes list, search, policy, profile, all 12 sector pages, and two scheme-detail pages) in English, Bengali and Hindi at 390 px and 1200 px wide, and checked for axe violations (colour contrast included), horizontal overflow, and touch targets under 48 px. Result: **0 problems in 114 page views**. It found, before the fix, programme source links under 48 px tall and an in-sector search that ignored the "benefit" and "who it is for" text: both fixed; the search fix has a test (`searchSchemes.test.ts`), the link size is checked only by this sweep.

The assistant steps ran with the model **made to fail** (a local stub answering 503), which is what proves the fallback; with a working key the same step passes on an answer.

## 7. What is not benchmarked

Server memory; the assistant under concurrent load; a cold start (index open, model load); a production deployment; a "before" load test; answer accuracy beyond the 16-question run above; abstention rate; and any user-perceived metric (time to interactive on a real phone and network). The numbers above are the ones to repeat after a change, with `scripts/benchmark_api.py`, `scripts/loadtest.py`, `python -m app.cli eval` and `frontend/e2e/journey.mjs`.
