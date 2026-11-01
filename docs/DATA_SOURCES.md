# Data sources

Which official documents CivicSaathi ingests, how each was checked, and which candidates were turned down and why. The machine-readable list is [backend/data/sources/scholarships.toml](../backend/data/sources/scholarships.toml); this file is the reasoning behind it. Everything below was observed on **2026-10-31**; websites change, so re-run `python -m app.cli verify` before relying on a detail.

## What goes in the registry

A source is added only if:

1. it is hosted on an official domain: `*.gov.in`, `*.nic.in`, or a host listed in `verification.py` together with the evidence that it is official;
2. a person has opened the URL and confirmed it is the real document, not a copy or a summary;
3. it downloads over HTTPS with a verifiable certificate, and `robots.txt` allows it;
4. it contains text, not only page images;
5. it adds something: a different scheme, issuer, format or kind of document.

## The registry

Two issuing bodies and two schemes, in three PDFs and one web page.

| Id                                   | Document                                    | Issuer                                          | Format        | Passages | Why it is here                                                                                                      |
| ------------------------------------ | ------------------------------------------- | ----------------------------------------------- | ------------- | -------: | ------------------------------------------------------------------------------------------------------------------- |
| `wb-svmcm-guidelines`                | SVMCM Scholarship: Guidelines               | Government of West Bengal                       | PDF           |       16 | A state scheme: income ceiling Rs 2,50,000, residency, marks. Fits the SPEC's state-scholarship tests (T1 to T4).   |
| `wb-svmcm-scheme-page`               | SVMCM: About the scheme (portal page)       | Government of West Bengal                       | web page      |       18 | A second official copy of the same rules, to cross-check against (rule R7). Its rate table is properly extractable. |
| `aicte-pragati-faq`                  | AICTE Pragati Scholarship: FAQs             | AICTE, Ministry of Education, Government of India | PDF         |       24 | A central scheme for girl students, written as questions and answers. Dated 2021, so it exercises rule R4.          |
| `aicte-pragati-notification-2026-27` | AICTE notification, applications open 2026-27 | AICTE                                         | PDF (scan)    |        5 | A current notification with deadlines. A scan with a hidden OCR layer, so it exercises SPEC test T7.                |

63 passages in total, in a ChromaDB collection embedded with `intfloat/multilingual-e5-small`.

## What the pipeline checks

Every check ends in `pass`, `warn` or `fail`. **One failure rejects the source** (and the index is left untouched); a warning keeps it, and travels with every passage as `verification = verified_with_warnings`.

| Check             | Looks at                                                                              | A failure means                                           |
| ----------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `official_domain` | The registry URL, before anything is downloaded                                       | Not an official host: nothing is downloaded              |
| `http_status`     | The response                                                                          | The server did not answer 200                             |
| `redirects`       | Every hop, checked before it is requested                                             | A redirect left official domains                          |
| `tls`             | Certificate chain and hostname against the OS trust store; expiry; legacy TLS mode    | Could not be verified (warns about legacy mode or expiry) |
| `file_type`       | File header and content type against the declared format                             | A PDF that is not a PDF, or a page that is a PDF          |
| `size`            | Against the 25 MB limit                                                               | Empty or too large                                        |
| `robots`          | The site's `robots.txt` (RFC 9309)                                                    | It forbids automated downloads (or cannot be read)       |
| `text_extracted`  | At least 200 characters                                                               | Probably a scan with no text layer                        |
| `identity`        | The registry's `expected_phrases` appear in the text                                  | This is not the document the registry describes           |
| `key_facts`       | The figures a person confirmed (`expected_facts`) still appear                        | _Warns_: the document may have changed                    |
| `document_date`   | Registry date, else PDF metadata, else `Last-Modified`                                | _Warns_ if older than 12 months (R4), unknown, or future  |
| `extraction`      | Problems reported by the reader, such as an OCR layer or undecodable characters       | _Warns_                                                   |

## Results

| Source                               | Size      | SHA-256 (prefix) | Document date                    | Warnings                                                          |
| ------------------------------------ | --------- | ---------------- | -------------------------------- | ----------------------------------------------------------------- |
| `wb-svmcm-guidelines`                | 63,772 B  | `765569e3615b`   | 2026-04-28 (PDF metadata)        | Legacy TLS mode (see below)                                       |
| `wb-svmcm-scheme-page`               | 47,904 B  | `a40d7064652b`   | none found                       | Legacy TLS mode; effective date unknown                           |
| `aicte-pragati-faq`                  | 869,830 B | `dd790e84cae3`   | 2021-11-10 (PDF metadata)        | Older than 12 months: may predate changes                         |
| `aicte-pragati-notification-2026-27` | 203,149 B | `b0ca55766a51`   | 2026-06-19 (printed on the letter) | Scan with OCR layer: verify figures and dates against the original |

**Cross-check of two official copies (rule R7).** The SVMCM guidelines exist as a PDF and as a portal page. A scripted comparison of their text found the same 22 distinct figures (amounts, percentages, years, dates) in both, and none in only one. Asking "what is the family income limit?" returns both copies. If the copies ever disagree, both will be returned, and a later stage can surface the conflict.

**Spot-checks of extraction.** The income ceiling (`Rs.2,50,000/-` per annum), the marks thresholds (60%, 53%, 55%, 45%), the scholarship rates (`1000/-`, `1500/-`, `2000/-`, `2500/-`, `5000/-`), the Pragati amount (`Rs. 50,000.00 per annum`) and the Pragati income limit (`Rs. 8 Lakh`) were read in the extracted text and keep their digits, separators and currency marks. For the SVMCM figures the independent web copy agrees. The FAQ and the notification have no second copy, so their figures were checked against the extracted text only, not against a rendering of the original pages.

### Findings worth knowing

- **`svmcm.wb.gov.in` needs a TLS exception, and says so.** The server only supports legacy TLS renegotiation (no RFC 5746), which OpenSSL 3 refuses by default (`UNSAFE_LEGACY_RENEGOTIATION_DISABLED`). Its two registry entries set `legacy_tls = true`: a per-source switch, documented in each entry's notes, that still verifies the certificate chain (DigiCert, wildcard `*.wb.gov.in`, valid until 2027-03-27) and the hostname. Every report carries a warning about it.
- **The AICTE notification is a scan, and its OCR has errors.** The text layer misreads the Hindi letterhead (it comes out as `fi. wFrr rer crdr+a w{rd ...`) and some dates: the verification deadline reads `3t't October.2026` and `1 5"' Novcmber.2026`. The application deadline `31 .10.2026` survived, and the identity and key-fact checks accept it. These passages are stored with `ocr = true`. Treat any figure from them as unverified until compared with the original.
- **The AICTE FAQ is from November 2021.** AICTE still links it as the Pragati FAQ, but it may predate changes; the report says so on every run.
- **PDF tables flatten.** The SVMCM rate table, extracted from the PDF, runs its columns together (`...Exam 1500/-UG (OTHER PROFESSIONAL`). On the web page the same table comes out one labelled row at a time (`COURSE: UG (SCIENCE); ... SCHOLARSHIP RATE PER MONTH (RS.): 1500/-`). Prefer the web copy for rates.

## Candidates evaluated and turned down

| Candidate                                                                                                 | What was found                                                                                                                                                                                                                                                                                              | Decision                                                      |
| --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| National Scholarship Portal documents (`scholarships.gov.in`): PM-USP/CSSS guidelines and FAQ, NSP FAQ    | The site's certificate (issued to NICSI by eMudhra, valid 2026-09-16 to 2026-12-15) is **revoked**: the issuing CA's OCSP responder reported "revoked, reason: superseded, revoked 2026-10-19" in a response produced on 2026-10-30, yet the site still served it. Windows and curl refuse the connection; Python's TLS stack does not check revocation and would have accepted it. | Excluded by hand. Re-evaluate once the site installs its replacement certificate. |
| `www.aicte-india.org` (AICTE's older domain)                                                              | The connection timed out after 90 seconds. `aicte.gov.in` serves the same pages.                                                                                                                                                                                                                            | Use `aicte.gov.in`                                            |
| NMMSS guidelines (`dsel.education.gov.in/.../NMMSS_Guidelines_22.pdf`)                                    | HTTP 404. The address came from a web search result and was stale: the reason every URL is verified at ingest time.                                                                                                                                                                                       | Dropped                                                       |
| AICTE "General Instructions (Pragati)" page (`aicte.gov.in`)                                              | Official and reachable, but the page is a list of links to documents, not prose. The documents it links to (FAQ, notification) were ingested instead.                                                                                                                                                      | Not ingested                                                  |

## Adding a source

1. Find the document on the issuing body's own domain, and open it. Confirm it is the real thing.
2. Note two to four phrases that appear in the real document and would not appear in a different one (`expected_phrases`), the one to three figures that matter most (`expected_facts`), and any date printed on it that is not in the file's metadata (`published_on`).
3. Add a `[[sources]]` table to a `.toml` file in `backend/data/sources/`. The header of `scholarships.toml` explains each field. For a web page, find the element that holds the content and set `content_selector` (browser developer tools, or look at the downloaded HTML).
4. Run `python -m app.cli verify <id>` and read every line. Fix a failing `identity` check by checking you picked the right URL; a failing `tls` check is the site's problem, not a reason to weaken verification.
5. Run `python -m app.cli ingest <id>`, then `search` for a few questions the document should answer.
6. Write what you found in the entry's `notes`, especially every warning and why it is acceptable.
7. Run `python -m pytest` (it checks that every registered URL is official and identifiable) and `python -m pytest -m live`.

## Known limits

Scans without a text layer are rejected (OCR is not built yet), tables in PDFs are flattened, and certificate revocation is not checked. See "Known limitations" in [ARCHITECTURE.md](ARCHITECTURE.md).
