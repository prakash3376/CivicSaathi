# Data flow

Three journeys: an official document becoming searchable evidence, a citizen browsing a programme, and a citizen asking a question.

## 1. From an official document to searchable evidence (run by a person)

```mermaid
flowchart LR
    R["data/sources/*.toml<br/>URL, issuer, identity phrases<br/>(added after a person opened the URL)"] --> V
    V["verify<br/>official host? robots.txt?<br/>TLS, redirects, file type, size"] -->|fails| X["rejected: the index is untouched;<br/>a transient download failure is retried<br/>with 2 s, 4 s, 8 s backoff"]
    V --> E["extract<br/>PDF (PDFium, per page) or HTML<br/>scan and OCR flagged"]
    E --> C["content checks<br/>identity phrases, key figures,<br/>document date"]
    C -->|fails| X
    C --> K["chunk<br/>about 900 characters, with page,<br/>section and clause kept"]
    K --> M["embed<br/>multilingual-e5-small,<br/>local, 384 dimensions"]
    M --> I["index in ChromaDB<br/>new passages written first,<br/>stale ones removed after"]
    I --> J["storage/jobs/ingest.json<br/>state of every source"]
    I --> S["change stamp<br/>readers reopen the index<br/>and drop their cached copies"]
```

Idempotent: a source's fingerprint (bytes, registry entry, extractor and chunker versions, embedding model) is compared before any work, so running it twice changes nothing. Previous document versions stay in `storage/raw/<id>/` named by hash; the index holds the latest.

## 2. A citizen browses a programme (no model, no login)

```mermaid
sequenceDiagram
    participant B as Browser (React)
    participant A as API (FastAPI)
    participant S as SchemeService (in memory)
    B->>A: GET /schemes (If-None-Match: previous hash)
    A->>S: catalogue() (records were loaded and checked at start)
    S-->>A: schemes + programmes
    A-->>B: 304 (no body) if unchanged, else 200 + ETag + gzip
    B->>A: GET /schemes/pm-kisan
    A-->>B: benefits, who, exclusions, documents, steps,<br/>each with the official words and where they are
    B->>A: POST /schemes/{id}/eligibility (only for a scheme with a check)
    A->>S: check(): a pure function of rules and answers
    A-->>B: eligible / not eligible / need more info, with the rule and its source
```

Nothing a visitor types is stored or logged. The browser keeps three choices (languages, reading speed) and nothing else.

## 3. A citizen asks a question

```mermaid
flowchart TD
    Q["Question + optional earlier questions + sector"] --> T["tidy, length check"]
    T --> G{"prompt injection or<br/>forgery request?"}
    G -->|yes| F1["fixed refusal, no model call"]
    G -->|no| P["remove personal numbers<br/>(Aadhaar, phone, PAN...)"]
    P --> IN["intent (rules, en/hi/bn)"]
    IN -->|"not about government"| F2["no search: 'the documents do not say'"]
    IN --> H["follow-up? add the earlier question<br/>to what is searched (never to the model)"]
    H --> RT["router: compare with catalogue entries<br/>and budget records by meaning"]
    RT --> D["dense search: the question's passages<br/>+ the routed records' documents,<br/>merged by reciprocal rank fusion,<br/>sector nudge, relevance floor"]
    D --> L["model drafts claims with exact quotes<br/>(Gemini, structured output)"]
    L --> VR["verify every claim:<br/>quote found word for word, every figure,<br/>month and address in the quote, right language"]
    VR -->|"some fail"| L2["one retry that says what was wrong"]
    L2 --> VR
    VR --> AN["answer: only claims that survived,<br/>citations with page, quote, dates, warnings"]
    L -->|"busy / down / unusable"| FB["fallback: the best passages,<br/>exactly as the documents have them"]
    AN --> TR["trace: intent, routed records, documents,<br/>timings, whether anything was dropped<br/>(no question text)"]
    FB --> TR
```

The model never sees the earlier questions, a personal number, or text the sanitiser flagged as an instruction. What it writes reaches the user only after the verification.
