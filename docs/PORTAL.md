# The portal: home, sectors, search, policy, profile, catalogue, budget

CivicSaathi opens on a home page that leads to twelve government sectors. This file says what exists, how the data is stored and checked, and what does not exist yet.

## What exists

| Route               | Page         | Data it shows                                                                    |
| ------------------- | ------------ | -------------------------------------------------------------------------------- |
| `/`                 | Home         | Search box (type or speak), 12 sector cards, featured schemes, latest updates    |
| `/schemes`          | Explore      | The 12 sectors, then every verified scheme with search and filters               |
| `/sectors/:id`      | A sector     | That sector's programmes, its budget records, its documents, questions, ask      |
| `/schemes/:id`      | A programme  | Full detail: a scheme with a check, or a programme or service that is read       |
| `/search?q=`        | Search       | Sectors, schemes and documents that contain every word typed                     |
| `/policy`           | Policy       | The indexed official documents, searchable, each with a link to the original     |
| `/profile`          | My Profile   | What the browser keeps (three choices), a button to clear them                   |
| `/ask?q=&scheme=&sector=` | AI Saathi | The one assistant; `q` fills the box (never sent for you); `scheme` or `sector` limit it to those documents |

## Where the data lives

There is no relational database. The data is **files that are checked**, and the **index** of the official documents they quote:

| Folder                      | Holds                                                                                   |
| --------------------------- | --------------------------------------------------------------------------------------- |
| `backend/data/sources/`     | The registry of official documents (URL, issuer, identity phrases). One TOML per group. |
| `backend/data/schemes/`     | Schemes with a questionnaire: rules, tracks, checklist (`docs/ELIGIBILITY.md`).         |
| `backend/data/catalogue/`   | Programmes and services that are read (`Entry`): benefits, who, exclusions, documents, steps, the official portal. |
| `backend/data/budget/`      | Budget records (`BudgetRecord`): figures by year and by kind.                           |
| `backend/storage/`          | Derived: the downloaded documents and the vector index. Safe to delete.                 |

`GET /api/v1/schemes` returns the schemes and the catalogue entries in one list (`layout` is `check` or `info`; `sectors` is a list, so one programme appears in every sector it truly belongs to and is written once). `GET /api/v1/schemes/{id}` returns the detail of either kind. `GET /api/v1/budget` returns the budget records. The assistant answers from the same indexed documents, limited by `source_ids` to a scheme's or a sector's documents.

### The trust rule

Every statement in an entry carries a **verbatim quote** from one of its registered sources. The loader refuses an entry whose figures, months or web addresses are not in the quote, whose quote is too short to mean anything, whose source is not registered, whose summary contains a figure (nothing backs it), or whose status is not "active" without a stated reason. `python -m app.cli catalogue-check` then checks that each quote is really in the downloaded document. Statements are English because the quotes are; the summary and the "who is it for" line are in English, Bengali and Hindi (drafts, needing a native speaker's review).

### Kinds

`scheme` (gives money, goods or cover), `service` (a registration, certificate or facility; steps and documents matter most) and `infrastructure` (builds roads, buses, stations, water or sanitation: shown with its purpose and public impact and a note that it pays no one). A programme that was merged, closed or discontinued stays in the catalogue, labelled, with a note.

### Budget

A budget record keeps its financial year and the kind of every figure: **Budget Estimate**, **Revised Estimate** or **Actual**. They are never mixed, and a record with no Actual says that its money is a plan, not money spent or received by citizens. An amount must be a number its quote states; wording may use the record's declared unit ("crore"). Earlier years' figures of the same document sit beside the current ones, which is the comparison.

## Commands (from `backend/`)

| Command                                      | Does                                                                          |
| -------------------------------------------- | ----------------------------------------------------------------------------- |
| `python -m app.cli verify [ID ...]`          | Download and check sources; index nothing                                     |
| `python -m app.cli fetch-text ID ... --out DIR` | Same checks, and save `<id>.txt` and `<id>.pages.txt` so quotes can be checked offline |
| `python -m app.cli ingest [ID ...]`          | Verify, chunk, embed and index sources (idempotent: unchanged sources are skipped) |
| `python -m app.cli catalogue`                | Records per sector, **counted from the data**                                 |
| `python -m app.cli catalogue-check`          | Every catalogue and budget quote must be found in its indexed document        |
| `python -m app.cli schemes-check`            | The same for the schemes with a questionnaire                                 |

Seeding is therefore: edit the TOML, `ingest` the new sources, `catalogue-check`. Running it twice changes nothing. A correction made by hand in a TOML file stays: nothing overwrites these files.

## Updates on the home page

A document counts as an update only if its `doc_type` is a notification, circular, order or amendment. Its date is the one the ingestion read from the document; one without a date shows "Date not found" and sorts last. Effective dates are not shown for documents because the ingestion does not extract them.

## Not built yet

- Uploading a notification or draft policy for a plain-language explanation; comparing two versions of a policy (`/policy` says so, with no button).
- An admin interface (records are edited in the TOML files and checked by the commands above), optional accounts, saved schemes, reminders.
- Source adapters for myScheme, India.gov.in, DBT Bharat and eGazette: they were used by people to find documents, not read by the code.
- Questionnaire eligibility for the new programmes: the catalogue lists who can get each one, with the official words; only the two scholarship schemes have a scored check.

## Privacy

The browser keeps three choices (interface language, answer language, reading speed). `/profile` shows them and clears them. Questions, eligibility answers and microphone audio are not stored by the site.
