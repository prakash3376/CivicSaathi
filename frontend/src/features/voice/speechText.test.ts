import { describe, expect, it } from 'vitest'
import { translator as schemeWords } from '@/features/schemes/strings'
import { answerBody, guidanceBody, notCoveredBody } from '@/test/utils'
import {
  eligibleBody,
  needMoreInfoBody,
  notEligibleBody,
  schemeDetailsBody,
} from '@/test/schemeFixtures'
import { answerSpeech, conversationSpeech, resultSpeech, schemeSpeech } from './speechText'

const track = schemeDetailsBody.tracks[0]!

describe('answerSpeech', () => {
  it('reads the claims, then the disclaimer, each sentence ending in a full stop', () => {
    const text = answerSpeech(answerBody)

    expect(text.startsWith("Your family's yearly income must not be more than Rs 2,50,000.")).toBe(
      true,
    )
    expect(text.endsWith('Check the official document before acting.')).toBe(true)
  })

  it('reads what the documents do not say and the warnings, with headings in the answer language', () => {
    const text = answerSpeech({
      ...answerBody,
      language: 'hi',
      claims: [{ text: 'आय सीमा से अधिक नहीं होनी चाहिए', citations: [1] }],
      not_stated: ['अंतिम तिथि'],
      warnings: [{ code: 'stale', message: 'दस्तावेज़ पुराना है।', source_ids: [] }],
      disclaimer: 'यह केवल जानकारी के लिए सारांश है।',
    })

    expect(text).toBe(
      'आय सीमा से अधिक नहीं होनी चाहिए. दस्तावेज़ों में जो नहीं कहा गया: अंतिम तिथि. ' +
        'कृपया ध्यान दें: दस्तावेज़ पुराना है। यह केवल जानकारी के लिए सारांश है।',
    )
  })

  it('reads the fixed message when the documents do not say', () => {
    const text = answerSpeech(notCoveredBody)

    expect(text).toContain('do not say this')
    expect(text).not.toContain('undefined')
  })

  it('does not add a full stop after a Hindi or Bengali danda', () => {
    expect(
      answerSpeech({
        ...answerBody,
        language: 'hi',
        claims: [{ text: 'वाक्य।', citations: [] }],
        disclaimer: 'सूचना।',
      }),
    ).not.toContain('।.')
  })
})

describe('general help', () => {
  it('says that it is not from a document before anything else, and ends with the question', () => {
    const text = conversationSpeech(guidanceBody, { first: false })

    expect(text.startsWith('I could not find this in the official documents')).toBe(true)
    expect(text).toContain('Most pension matters are handled by the block or district office.')
    expect(text.endsWith('Which state do you live in?')).toBe(true)
  })

  it('is read by the Listen button too, with the disclaimer', () => {
    const text = answerSpeech(guidanceBody)

    expect(text.startsWith('I could not find this')).toBe(true)
    expect(text).toContain('Check the official document before acting.')
  })

  it('invites the next question when there is none of its own', () => {
    const text = conversationSpeech({ ...guidanceBody, follow_up: '' }, { first: false })

    expect(text.endsWith('Is there anything else you would like to ask?')).toBe(true)
  })

  it('is read in the language of the answer, not of the page', () => {
    const text = conversationSpeech(
      { ...answerBody, language: 'hi', claims: [{ text: 'आय सीमा।', citations: [1] }] },
      { first: false },
    )

    expect(text.startsWith('सरकारी दस्तावेज़ों में यह लिखा है।')).toBe(true)
    expect(text.endsWith('क्या आप कुछ और पूछना चाहेंगे?')).toBe(true)
  })
})

describe('conversationSpeech', () => {
  it('leads in, answers, reads the disclaimer the first time, and invites the next question', () => {
    const text = conversationSpeech(answerBody, { first: true })

    expect(text).toBe(
      'Here is what the official documents say. ' +
        "Your family's yearly income must not be more than Rs 2,50,000. " +
        'Informational summary, not legal advice. Check the official document before acting. ' +
        'Is there anything else you would like to ask?',
    )
  })

  it('leaves the disclaimer to the screen after the first answer', () => {
    const text = conversationSpeech(answerBody, { first: false })

    expect(text).not.toContain('legal advice')
    expect(text.endsWith('Is there anything else you would like to ask?')).toBe(true)
  })

  it('says a greeting and nothing else: no disclaimer after "hello"', () => {
    const text = conversationSpeech(
      { ...notCoveredBody, conversational: true, text: 'Hello! I am CivicSaathi.' },
      { first: true },
    )

    expect(text).toBe('Hello! I am CivicSaathi.')
  })

  it('does not pretend to invite more after a failure or a refusal', () => {
    const text = conversationSpeech(notCoveredBody, { first: false })

    expect(text).not.toContain('anything else')
  })
})

describe('resultSpeech', () => {
  it.each([
    ['en', 'You appear to meet every rule we checked'],
    ['bn', 'আমাদের দেখা সব নিয়ম আপনি পূরণ করছেন বলে মনে হচ্ছে'],
    ['hi', 'लगता है आप हमारे जाँचे गए सभी नियम पूरे करते हैं'],
  ] as const)('starts with the outcome, in %s', (language, heading) => {
    expect(resultSpeech(eligibleBody, track, schemeWords(language)).startsWith(heading)).toBe(true)
  })

  it('reads every rule with its status, the documents, the steps and the disclaimer', () => {
    const text = resultSpeech(eligibleBody, track, schemeWords('en'))

    expect(text).toContain('Met: Family income is at most Rs 2,50,000 a year.')
    expect(text).toContain('Documents you need: Bank account details.')
    expect(text).toContain('Documents you may need: Proof of family income.')
    expect(text).toContain('How to apply: Apply online on the scholarship portal.')
    expect(text.endsWith('Check the official document before acting.')).toBe(true)
  })

  it('reads what is still needed only when answering can change the result', () => {
    const more = resultSpeech(needMoreInfoBody, track, schemeWords('en'))
    const final = resultSpeech(notEligibleBody, track, schemeWords('en'))

    expect(more).toContain('Still needed: What is your family income in a year?')
    expect(final).not.toContain('Still needed')
    expect(final).toContain('Not met: Family income is at most Rs 2,50,000 a year.')
  })

  it('reads in the language of the interface', () => {
    const text = resultSpeech(eligibleBody, track, schemeWords('hi'))

    expect(text).toContain('पूरा हुआ: पारिवारिक आय प्रति वर्ष अधिकतम 2,50,000 रुपये है')
  })
})

describe('schemeSpeech', () => {
  it('reads the name, the benefit, who can get it, what to gather and how to apply', () => {
    const text = schemeSpeech(schemeDetailsBody, track, schemeWords('en'))

    expect(text.startsWith('Swami Vivekananda')).toBe(true)
    expect(text).toContain('What you get: Rs 1,000 a month for 10 months.')
    expect(text).toContain('Who can get it: Family income is at most Rs 2,50,000 a year.')
    expect(text).toContain('Documents to gather: Bank account details.')
    expect(text).toContain('How to apply: Apply online on the scholarship portal.')
    expect(text).toContain('The documents do not say: The last date to apply.')
  })

  it('reads the scheme without a course too', () => {
    const text = schemeSpeech(schemeDetailsBody, undefined, schemeWords('en'))

    expect(text).not.toContain('What you get')
    expect(text).toContain('How to apply')
  })
})
