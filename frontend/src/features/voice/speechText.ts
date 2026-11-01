/**
 * What is read aloud: the same words the screen shows, put in reading order. Nothing is added
 * that the page does not say, and the disclaimer (SPEC rule R6) is read at the end (in a spoken
 * conversation, at the first answer; see `conversationSpeech`).
 * Each text is in one language, so that one voice can read it.
 */
import type { Answer, EligibilityResult, SchemeDetails, TrackView } from '@/api/types'
import { translator as assistantWords } from '@/features/assistant/strings'
import { statusOf } from '@/features/schemes/criterionStatus'
import { deadlineText } from '@/features/schemes/deadlineText'
import type { Translate as SchemeWords } from '@/features/schemes/strings'
import { local } from '@/i18n/translator'
import { translator as voiceWords } from './strings'

/** Sentences end in a full stop so that the speaker pauses between items. */
const sentence = (text: string) => (/[.!?:\u{0964}]$/u.test(text) ? text : `${text}.`)

/** How an answer is put into speech: the page's reading order, or a spoken conversation. */
interface AnswerSpeechStyle {
  /** Say a short lead-in before what the documents say, and end by inviting the next question. */
  conversation: boolean
  /** Read the disclaimer (SPEC rule R6). It is always on the screen. */
  disclaimer: boolean
}

function speechParts(answer: Answer, style: AnswerSpeechStyle): string[] {
  // A greeting or thanks is not an explainer: there is nothing to disclaim, and reading a legal
  // line after "hello" is what makes a voice sound like a machine.
  if (answer.conversational) return [answer.text]

  const words = assistantWords(answer.language)
  const talk = voiceWords(answer.language)
  const parts: string[] = []

  if (answer.guidance) {
    // General help comes after the fixed words that say it is not from an official document.
    if (answer.guidance_intro) parts.push(answer.guidance_intro)
    parts.push(answer.text)
  } else if (answer.answerable) {
    if (style.conversation) parts.push(talk('talkLeadDocs'))
    parts.push(...answer.claims.map((claim) => claim.text))
  } else {
    parts.push(answer.text)
  }

  if (answer.not_stated.length > 0) {
    parts.push(`${words('notStatedHeading')}:`, ...answer.not_stated)
  }
  if (answer.warnings.length > 0) {
    parts.push(`${words('noteHeading')}:`, ...answer.warnings.map((warning) => warning.message))
  }
  if (style.disclaimer) parts.push(answer.disclaimer)

  // The last thing said is the question the person is about to answer.
  if (answer.follow_up) parts.push(answer.follow_up)
  else if (style.conversation && (answer.answerable || answer.guidance)) {
    parts.push(talk('talkAnythingElse'))
  }
  return parts
}

/** An answer in the language it was written in: its claims, what is not said, warnings, disclaimer. */
export function answerSpeech(answer: Answer): string {
  const parts = speechParts(answer, { conversation: false, disclaimer: true })
  return parts.map(sentence).join(' ')
}

/**
 * An answer as it is said in a spoken conversation: a lead-in, the answer, and a question that
 * invites the next one. The disclaimer is read in full at the first answer of a conversation and
 * is left to the screen afterwards, so that it is not repeated after every turn.
 */
export function conversationSpeech(answer: Answer, options: { first: boolean }): string {
  const parts = speechParts(answer, { conversation: true, disclaimer: options.first })
  return parts.map(sentence).join(' ')
}

/** An eligibility result in the language of the interface. */
export function resultSpeech(result: EligibilityResult, track: TrackView, t: SchemeWords): string {
  const language = t.language
  const headings = {
    eligible: ['outcomeEligible', 'outcomeEligibleText'],
    not_eligible: ['outcomeNot', 'outcomeNotText'],
    need_more_info: ['outcomeMore', 'outcomeMoreText'],
  } as const
  const [headingKey, textKey] = headings[result.outcome]
  const parts = [t(headingKey), t(textKey)]

  if (result.outcome === 'need_more_info') {
    const asked = result.unanswered.flatMap((field) => {
      const question = track.questions.find((candidate) => candidate.field === field)
      return question ? [local(question.text, language)] : []
    })
    if (asked.length > 0) parts.push(`${t('stillNeeded')}:`, ...asked)
  }

  parts.push(`${t('rulesHeading')}:`)
  for (const criterion of result.criteria) {
    parts.push(`${t(statusOf(criterion).word)}: ${local(criterion.label, language)}`)
  }
  if (result.caveats.length > 0) {
    parts.push(`${t('caveatsHeading')}:`, ...result.caveats.map((c) => local(c.text, language)))
  }

  const documents = (applicability: 'needed' | 'maybe') =>
    result.checklist.documents
      .filter((document) => document.applicability === applicability)
      .map((document) => local(document.label, language))
  const needed = documents('needed')
  const maybe = documents('maybe')
  if (needed.length > 0) parts.push(`${t('checklistNeededNow')}:`, ...needed)
  if (maybe.length > 0) parts.push(`${t('checklistMaybe')}:`, ...maybe)
  if (result.checklist.deadlines.length > 0) {
    parts.push(...result.checklist.deadlines.map((deadline) => deadlineText(deadline, t)))
  }
  if (result.checklist.steps.length > 0) {
    parts.push(
      `${t('stepsHeading')}:`,
      ...result.checklist.steps.map((s) => local(s.text, language)),
    )
  }
  parts.push(local(result.disclaimer, language))
  return parts.map(sentence).join(' ')
}

/** One course of a scheme in the language of the interface. */
export function schemeSpeech(
  scheme: SchemeDetails,
  track: TrackView | undefined,
  t: SchemeWords,
): string {
  const language = t.language
  const parts = [scheme.name, local(scheme.summary, language)]
  if (scheme.deadlines.length > 0) {
    parts.push(...scheme.deadlines.map((deadline) => deadlineText(deadline, t)))
  }
  if (track) {
    parts.push(
      `${local(track.label, language)}.`,
      `${t('benefitHeading')}:`,
      local(track.benefit.text, language),
    )
    parts.push(`${t('criteriaHeading')}:`, ...track.criteria.map((c) => local(c.label, language)))
    parts.push(`${t('documentsHeading')}:`, ...track.documents.map((d) => local(d.label, language)))
  }
  parts.push(`${t('stepsHeading')}:`, ...scheme.steps.map((step) => local(step.text, language)))
  if (scheme.not_stated.length > 0) {
    parts.push(
      `${t('notStatedHeading')}:`,
      ...scheme.not_stated.map((item) => local(item, language)),
    )
  }
  return parts.map(sentence).join(' ')
}
