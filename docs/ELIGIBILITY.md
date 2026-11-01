# Eligibility

How CivicSaathi decides whether someone qualifies for a scholarship, what the three outcomes mean, how a scheme is written down as data, and what the result does and does not promise. Product rules R1 to R3 and acceptance criteria AC5 and AC6 are in [SPEC.md](../SPEC.md); the code is in `backend/app/services/eligibility/`.

## What it guarantees

- **No language model decides.** The result is computed by a pure Python function from the scheme's rules and the person's answers. The same answers always give the same result, whatever order they arrive in (AC5).
- **A skipped question never gives "eligible"** (AC6). An answer that is missing is an _unknown_, and an unknown is never turned into yes or no.
- **Every rule carries the official words.** Each criterion, document, step, contact, date and benefit names the source document and quotes it. `schemes-check` proves the quote is still in the indexed document.
- **Numbers are exact.** A figure, month or address in the English or Bengali wording must appear in the quote it cites; a rule's value must be in its quote. A scheme file that breaks this does not load.
- **Answers are never stored or logged.** They are used to build one response. Errors name the question, never the submitted value. The response is `Cache-Control: no-store`.

## The three outcomes

| Outcome          | When                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------- |
| `not_eligible`   | At least one required criterion is **definitely** not met. Nothing answered later can change it, so it stands even if other questions were skipped. |
| `need_more_info` | No criterion is definitely failed, but at least one is unknown. The result lists the questions still needed (`unanswered`). |
| `eligible`       | Every required criterion is met, with every question it depends on answered.          |

A criterion can have an exemption the document states ("Not applicable for Board Toppers"): `waived_when`. If the person is exempt the criterion is met and marked as waived. If a criterion fails but the exemption's question is unanswered, the criterion is _unknown_, not failed: the person may be exempt, so "no" would be a guess.

Whether a boundary counts is written into the rule, from the document's own wording: "less than Rs. 8 Lakh" is `lt 800000` (Rs 8,00,000 exactly is **not** eligible); "not more than Rs. 2,50,000" is `lte 250000` (exactly Rs 2,50,000 **is**); "at least 60%" is `gte 60`.

"Eligible" means _the rules we checked are met_. Each result also lists what the questionnaire cannot decide (`caveats`, for example institution approval) and ends with the standing disclaimer (R6).

## Writing a scheme

Schemes are data in `backend/data/schemes/`, never code:

- `fields.toml`: every question that can be asked, once (type `yes_no`, `number` or `choice`, wording in English, Bengali and Hindi, hint, unit, limits, and how a number is shown back).
- one file per scheme: its identity and sources, **tracks** (a course or group with its own rules and benefit), criteria and documents shared by all tracks (a track skips some with `omit_common`), steps, contacts, deadlines, where to apply, and `not_stated` (what a person might expect but the documents do not say: rule R1).

To add or change a scheme:

1. Read the official documents. Register them first (see [DATA_SOURCES.md](DATA_SOURCES.md)) and `ingest`.
2. Write the TOML. Copy a quote word for word; write figures with the digits 0-9 in all three languages (`en`, `bn`, `hi`: a statement without Hindi does not load). Add a `not_stated` entry only after searching the documents and finding nothing.
3. `python -m app.cli schemes` loads and lists it. A load error says which rule and why.
4. `python -m app.cli schemes-check` checks every quote against the indexed documents. It must report 0 problems.
5. Add tests (see `tests/test_eligibility_service.py` for boundaries and the all-subsets AC6 check), and have a native speaker review the Bengali and the Hindi.

## API

| Endpoint                                  | Returns                                                             |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `GET /api/v1/schemes`                     | The catalogue: name, authority, summary, courses, deadline status   |
| `GET /api/v1/schemes/{id}`                | One scheme: per course the rules (with quotes), questions, documents, benefit; steps, contacts, dates, what is not stated |
| `POST /api/v1/schemes/{id}/eligibility`   | `{track, answers}` in; outcome, each criterion's status and quote, unanswered questions, caveats, checklist out |

A deadline's status (`open`, `closes_today`, `closed`) is computed from today's date on each request. If the rule files fail to load, these endpoints answer `503 schemes_unavailable` and the rest of the API, `/health` included, keeps working.

## Limits

- Two schemes (AICTE Pragati, West Bengal SVMCM) are written so far. Both documents are public; rules were checked only against those documents, not against the scheme administrators.
- The AICTE deadline comes from a scanned notice; it is flagged as read from a scan and must be checked on the official site.
- The questionnaire cannot verify anything (income certificates, approvals, marks); it takes the person's word and says what to check.
- The Bengali and Hindi wording of the rules and screens are drafts by a non-native speaker and need a native speaker's review.
