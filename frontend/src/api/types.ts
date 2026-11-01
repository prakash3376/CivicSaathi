/** Reply of `GET /api/v1/health`. Mirrors `app.schemas.health.HealthResponse` in the backend. */
export interface HealthResponse {
  status: 'ok'
  service: string
  version: string
  environment: string
  /** ISO 8601, UTC. */
  timestamp: string
  uptime_seconds: number
}

/** The languages an answer can be written in. */
export type AnswerLanguage = 'en' | 'bn' | 'hi'
/** What the user picks: a language, or 'auto' to follow the language of the question. */
export type LanguageChoice = 'auto' | AnswerLanguage

/** Body of `POST /api/v1/assistant/ask`. Mirrors `app.schemas.assistant.AskRequest`. */
export interface AskRequest {
  question: string
  language: LanguageChoice
  /** Only answer from these sources; by default, from all. */
  source_ids?: string[]
  /** Earlier questions of the conversation, to find the evidence for a follow-up. */
  history?: string[]
  /** The sector being looked at: a nudge, never a limit. */
  sector?: SectorId
}

/** Where a quote sits in its passage. Counts Unicode code points, as Python does. */
export interface Highlight {
  start: number
  end: number
}

/** Mirrors `app.domain.assistant.Citation`. */
export interface Citation {
  number: number
  source_id: string
  title: string
  authority: string
  url: string
  page_start: number | null
  page_end: number | null
  section: string
  clause: string
  /** The full text of the cited passage, as in the document. */
  passage: string
  /** The words of the passage that support the claim. */
  quote: string
  /** Language of the passage and quote ('en', 'bn', 'hi', ...), for `lang` attributes; may be null. */
  language: string | null
  highlights: Highlight[]
  /** ISO date (YYYY-MM-DD). */
  document_date: string | null
  date_source: string | null
  /** ISO 8601. */
  verified_at: string | null
  verification: string
  age_days: number | null
  /** Older than 12 months. */
  stale: boolean
  /** Read from a scan, so figures may be misread. */
  ocr: boolean
}

export interface AnswerClaim {
  text: string
  /** Numbers of the citations this claim rests on. */
  citations: number[]
}

export interface AnswerWarning {
  code: string
  message: string
  source_ids: string[]
}

/** Reply of `POST /api/v1/assistant/ask`. Mirrors `app.domain.assistant.Answer`. */
export interface Answer {
  /** False when the documents do not say, or the question was refused. `text` then says why. */
  answerable: boolean
  language: AnswerLanguage
  text: string
  claims: AnswerClaim[]
  citations: Citation[]
  /** Parts of the question the documents do not cover. */
  not_stated: string[]
  warnings: AnswerWarning[]
  disclaimer: string
  model: string | null
  /** What the question was judged to be for. */
  intent?: string | null
  /** The model could not answer: the citations are the best-matching passages, unexplained. */
  fallback?: boolean
  /**
   * The documents do not cover the question, so `text` is general help that does NOT come from an
   * official document (no citations, no figures). `guidance_intro` says so and is shown or read
   * before it.
   */
  guidance?: boolean
  guidance_intro?: string
  /** A short question that keeps a conversation going; only with `guidance`. */
  follow_up?: string
  /** A greeting, thanks or "who are you": not an explainer, so nothing to cite. */
  conversational?: boolean
}

/** Mirrors `app.domain.assistant.SourceSummary`. */
export interface SourceSummary {
  id: string
  title: string
  scheme: string
  authority: string
  level: string
  state: string | null
  doc_type: string
  format: string
  url: string
  passages: number
  document_date: string | null
  date_source: string | null
  verified_at: string | null
  verification: string
  age_days: number | null
  stale: boolean
  verification_due: boolean
  ocr: boolean
}

/** Reply of `GET /api/v1/sources`. */
export interface SourcesResponse {
  sources: SourceSummary[]
}

/** Body of every error reply. Mirrors `app.schemas.errors.ErrorResponse` in the backend. */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    request_id?: string
    details?: { loc: (string | number)[]; message: string; type: string }[]
  }
}

// --- Schemes and eligibility. Mirror `app.domain.eligibility` in the backend. ---------------------

/** Wording in both languages. Figures are written with the digits 0-9. */
export interface LocalText {
  en: string
  bn: string
  hi: string
}

/** Words of an official document that support a statement, word for word. */
export interface Evidence {
  source_id: string
  quote: string
  /** Where in the document ("page 4"), when the record says. */
  where?: string
}

export interface Choice {
  id: string
  label: LocalText
}

/** One question of the questionnaire. Answering is always optional. */
export interface Question {
  field: string
  type: 'number' | 'yes_no' | 'choice'
  text: LocalText
  hint: LocalText | null
  unit: LocalText | null
  choices: Choice[]
  minimum: number | null
  maximum: number | null
  integer: boolean
}

/** What a person may answer: yes or no, a number, a choice id; `null` or missing is skipped. */
export type AnswerValue = boolean | number | string | null
export type Answers = Record<string, AnswerValue>

export type Outcome = 'eligible' | 'not_eligible' | 'need_more_info'
export type CriterionStatus = 'met' | 'not_met' | 'unknown'
export type DeadlineStatus = 'open' | 'closes_today' | 'closed'

export interface TrackStub {
  id: string
  label: LocalText
}

export interface DeadlineView {
  id: string
  label: LocalText
  /** ISO date (YYYY-MM-DD). */
  on: string
  status: DeadlineStatus
  /** Null once it has passed. */
  days_left: number | null
  /** Read from a scan, so the date may be misread. */
  scanned: boolean
  evidence: Evidence[]
}

/** The sectors a scheme can belong to. Mirrors `Sector` in `app.domain.eligibility`. */
export type SectorId =
  | 'education'
  | 'health'
  | 'agriculture'
  | 'women-child'
  | 'employment'
  | 'housing'
  | 'social-welfare'
  | 'business'
  | 'transport'
  | 'budget'
  | 'environment'
  | 'public-services'

export type EntryKind = 'scheme' | 'service' | 'infrastructure'
export type EntryStatus = 'active' | 'closed' | 'discontinued' | 'merged'

/** One card of the catalogue: a scheme with an eligibility check, or a programme or service to read. */
export interface SchemeSummary {
  id: string
  name: string
  authority: string
  level: 'central' | 'state'
  state: string | null
  /** One programme may sit in several sectors. */
  sectors: SectorId[]
  /** 'check' has a questionnaire and a checklist; 'info' is read. */
  layout: 'check' | 'info'
  kind: EntryKind
  status: EntryStatus
  /** Who it is for, in words (information programmes only). */
  target: LocalText | null
  /** The first verified benefit, in English (information programmes only). */
  benefit: string | null
  last_verified: string | null
  summary: LocalText
  /** The documents the scheme rests on: the scope of a question about it. */
  source_ids: string[]
  tracks: TrackStub[]
  deadline: DeadlineView | null
}

/** Reply of `GET /api/v1/schemes`. */
export interface SchemesResponse {
  schemes: SchemeSummary[]
}

export interface CriterionView {
  id: string
  label: LocalText
  note: LocalText | null
  evidence: Evidence[]
}

export interface ChecklistDocument {
  id: string
  label: LocalText
  detail: LocalText | null
  /** "maybe" while it depends on an answer not given yet, or the document says "if applicable". */
  applicability: 'needed' | 'maybe'
  evidence: Evidence[]
}

export interface Caveat {
  id: string
  text: LocalText
  evidence: Evidence[]
}

export interface Benefit {
  text: LocalText
  evidence: Evidence[]
}

export interface Step {
  id: string
  text: LocalText
  evidence: Evidence[]
}

export interface Contact {
  id: string
  label: LocalText
  /** An e-mail address or a phone number, exactly as in the document. */
  value: string
  evidence: Evidence[]
}

export interface Apply {
  text: LocalText
  url: string
  evidence: Evidence[]
}

export interface TrackView {
  id: string
  label: LocalText
  description: LocalText | null
  benefit: Benefit
  criteria: CriterionView[]
  questions: Question[]
  documents: ChecklistDocument[]
  caveats: Caveat[]
}

/** Reply of `GET /api/v1/schemes/{id}`. */
export interface SchemeDetails {
  layout: 'check'
  id: string
  name: string
  authority: string
  level: 'central' | 'state'
  state: string | null
  sectors: SectorId[]
  summary: LocalText
  source_ids: string[]
  tracks: TrackView[]
  steps: Step[]
  contacts: Contact[]
  deadlines: DeadlineView[]
  apply: Apply
  /** What a person may expect to find that the documents do not say. */
  not_stated: LocalText[]
}

/** Body of `POST /api/v1/schemes/{id}/eligibility`. Never stored by the server. */
export interface EligibilityRequest {
  track: string
  answers: Answers
}

export interface CriterionResult {
  id: string
  label: LocalText
  status: CriterionStatus
  /** Not required of this person, because of an exemption the document states. */
  waived: boolean
  field: string
  /** What the person answered, in words. */
  answer_text: LocalText | null
  note: LocalText | null
  evidence: Evidence[]
}

export interface Checklist {
  documents: ChecklistDocument[]
  steps: Step[]
  contacts: Contact[]
  deadlines: DeadlineView[]
  apply: Apply
  not_stated: LocalText[]
}

/** Reply of `POST /api/v1/schemes/{id}/eligibility`. */
export interface EligibilityResult {
  scheme_id: string
  track_id: string
  outcome: Outcome
  criteria: CriterionResult[]
  /** Fields of the questions still needed, in the order they are asked. */
  unanswered: string[]
  caveats: Caveat[]
  checklist: Checklist
  disclaimer: LocalText
}

// --- Programmes and services (no questionnaire), and the budget -----------------------------------

/** A fact in English with the official words that say so. */
export interface Statement {
  text: string
  evidence: Evidence[]
}

export interface ProgrammeLink {
  label: string
  url: string
  evidence: Evidence[]
}

export interface SourceRef {
  id: string
  title: string
  url: string
}

/** Reply of `GET /api/v1/schemes/{id}` for a programme or service. */
export interface ProgrammeDetails {
  layout: 'info'
  id: string
  name: string
  kind: EntryKind
  sectors: SectorId[]
  authority: string
  level: 'central' | 'state'
  state: string | null
  applicable_states: string[]
  status: EntryStatus
  status_note: string
  summary: LocalText
  target: LocalText
  source_ids: string[]
  last_verified: string
  published_on: string | null
  effective_on: string | null
  benefits: Statement[]
  eligibility: Statement[]
  exclusions: Statement[]
  documents: Statement[]
  steps: Statement[]
  apply: ProgrammeLink
  not_stated: string[]
  sources: SourceRef[]
}

export type FigureBasis = 'budget_estimate' | 'revised_estimate' | 'actual'

export interface BudgetFigure {
  basis: FigureBasis
  year: string
  amount: number
  unit: 'crore' | 'lakh_crore' | 'percent'
  evidence: Evidence[]
}

/** A budget record. A figure is an estimate or an actual, never mixed; see `not_actual_spending`. */
export interface BudgetRecord {
  id: string
  budget_year: string
  level: 'central' | 'state'
  state: string | null
  sector: SectorId | null
  kind: 'allocation' | 'announcement' | 'tax'
  title: string
  department: string
  last_verified: string
  summary: LocalText
  meaning: string
  figures: BudgetFigure[]
  statements: Statement[]
  sources: SourceRef[]
  not_actual_spending: boolean
}

export interface BudgetResponse {
  records: BudgetRecord[]
}
