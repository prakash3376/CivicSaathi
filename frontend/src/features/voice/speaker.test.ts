import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { installSpeech, resetSpeaker } from '@/test/speech'
import { pickVoice, speaker, splitForSpeech } from './speaker'

const voice = (lang: string, name = lang) => ({ lang, name }) as SpeechSynthesisVoice

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  resetSpeaker()
  speaker.setRate('normal')
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('pickVoice', () => {
  it('prefers the English of India, then any other English', () => {
    const voices = [voice('en-US'), voice('en-IN'), voice('en-GB')]

    expect(pickVoice(voices, 'en')?.lang).toBe('en-IN')
    expect(pickVoice([voice('en-US'), voice('en-GB')], 'en')?.lang).toBe('en-GB')
  })

  it('finds Bengali and Hindi voices, whichever way the browser writes the tag', () => {
    expect(pickVoice([voice('en-US'), voice('bn_BD')], 'bn')?.lang).toBe('bn_BD')
    expect(pickVoice([voice('en-US'), voice('hi-IN')], 'hi')?.lang).toBe('hi-IN')
    expect(pickVoice([voice('HI-in')], 'hi')?.lang).toBe('HI-in')
  })

  it('never lends a voice of another language', () => {
    const english = [voice('en-IN'), voice('en-US')]

    expect(pickVoice(english, 'bn')).toBeNull()
    expect(pickVoice(english, 'hi')).toBeNull()
    expect(pickVoice([voice('bn-IN')], 'hi')).toBeNull()
    expect(pickVoice([], 'en')).toBeNull()
  })
})

describe('splitForSpeech', () => {
  it('keeps a short text whole', () => {
    expect(splitForSpeech('Income must be at most Rs 2,50,000.')).toEqual([
      'Income must be at most Rs 2,50,000.',
    ])
  })

  it('cuts at sentence ends, joining short sentences up to the limit', () => {
    const text = 'One is here. Two is here. Three is here. Four is here.'

    expect(splitForSpeech(text, 30)).toEqual([
      'One is here. Two is here.',
      'Three is here. Four is here.',
    ])
  })

  it('cuts after the Hindi and Bengali danda too', () => {
    expect(splitForSpeech('पहला वाक्य यहाँ है। दूसरा वाक्य यहाँ है।', 25)).toEqual([
      'पहला वाक्य यहाँ है।',
      'दूसरा वाक्य यहाँ है।',
    ])
    expect(splitForSpeech('প্রথম বাক্য এখানে। দ্বিতীয় বাক্য এখানে।', 22)).toHaveLength(2)
  })

  it('cuts a long sentence at a space, never inside a word, and loses nothing', () => {
    const text = Array.from({ length: 60 }, (_, i) => `word${i}`).join(' ')

    const pieces = splitForSpeech(text, 50)

    expect(pieces.every((piece) => piece.length <= 50)).toBe(true)
    expect(pieces.join(' ')).toBe(text)
    for (const piece of pieces) expect(piece).not.toMatch(/^\s|\s$/)
  })

  it('has nothing to say for an empty text', () => {
    expect(splitForSpeech('   \n ')).toEqual([])
  })
})

describe('the speaker', () => {
  const voices = [
    { lang: 'en-IN', name: 'English India' },
    { lang: 'hi-IN', name: 'Hindi India' },
  ]

  it('reads a text piece by piece with the voice of its language, then goes quiet', () => {
    const speech = installSpeech(voices)
    const text = `${'a'.repeat(100)}. ${'b'.repeat(100)}. ${'c'.repeat(100)}.`

    expect(speaker.speak('x', text, 'en')).toBe(true)
    expect(speaker.getSnapshot().playingId).toBe('x')
    expect(speech.spoken()).toHaveLength(1) // one at a time: the next waits for the end
    speech.finishPiece()
    speech.finishPiece()
    expect(speaker.getSnapshot().playingId).toBe('x')
    speech.finishPiece()

    expect(speech.spoken().map((piece) => piece.text[0])).toEqual(['a', 'b', 'c'])
    expect(speech.spoken().every((piece) => piece.voice === 'English India')).toBe(true)
    expect(speech.spoken().every((piece) => piece.lang === 'en-IN')).toBe(true)
    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('reads Hindi with the Hindi voice', () => {
    const speech = installSpeech(voices)

    speaker.speak('x', 'यह एक वाक्य है।', 'hi')

    expect(speech.spoken()[0]).toMatchObject({ voice: 'Hindi India', lang: 'hi-IN' })
  })

  it('refuses, and says so, when the device has no voice for the language', () => {
    const speech = installSpeech(voices)

    expect(speaker.speak('x', 'এটি একটি বাক্য।', 'bn')).toBe(false)

    expect(speech.spoken()).toEqual([])
    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('refuses when the browser has no speech at all', () => {
    expect(speaker.supported()).toBe(false)
    expect(speaker.speak('x', 'Hello there.', 'en')).toBe(false)
  })

  it('refuses a text with nothing to say', () => {
    installSpeech(voices)

    expect(speaker.speak('x', '  ', 'en')).toBe(false)
  })

  it('stops at once, and ignores the end events that come after', () => {
    const speech = installSpeech(voices)
    speaker.speak('x', `${'a'.repeat(100)}. ${'b'.repeat(100)}.`, 'en')

    speaker.stop()
    speech.finishPiece()

    expect(speech.synthesis.cancel).toHaveBeenCalled()
    expect(speaker.getSnapshot().playingId).toBeNull()
    expect(speech.spoken()).toHaveLength(1) // the second piece was never started
  })

  it('reads one thing at a time: starting another ends the first', () => {
    const speech = installSpeech(voices)
    speaker.speak('first', 'The first text is long enough.', 'en')

    speaker.speak('second', 'The second text.', 'en')

    expect(speaker.getSnapshot().playingId).toBe('second')
    expect(speech.spoken().map((piece) => piece.text)).toEqual([
      'The first text is long enough.',
      'The second text.',
    ])
  })

  it('does not let the interruption of the first reading end the second', () => {
    const speech = installSpeech(voices)
    speaker.speak('first', 'First text here.', 'en')
    speaker.speak('second', 'Second text here.', 'en')

    // cancel() has already told the first utterance it was interrupted; the second plays on.
    expect(speaker.getSnapshot().playingId).toBe('second')
    speech.finishPiece()
    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('goes quiet if the browser reports an error', () => {
    const speech = installSpeech(voices)
    speaker.speak('x', 'Some text here.', 'en')

    speech.synthesis.cancel() // reported to the utterance as an error

    expect(speaker.getSnapshot().playingId).toBeNull()
  })

  it('tells the caller once that a reading ended at its end', () => {
    const speech = installSpeech(voices)
    const ended = vi.fn()
    speaker.speak('x', `${'a'.repeat(100)}. ${'b'.repeat(100)}.`, 'en', ended)

    speech.finishPiece()
    expect(ended).not.toHaveBeenCalled() // one piece is still to be read
    speech.finishPiece()

    expect(ended).toHaveBeenCalledOnce()
    expect(ended).toHaveBeenCalledWith(true)
  })

  it('tells the caller, once, that a reading was stopped', () => {
    installSpeech(voices)
    const ended = vi.fn()
    speaker.speak('x', 'A text to be stopped.', 'en', ended)

    speaker.stop()
    speaker.stop()

    expect(ended).toHaveBeenCalledOnce()
    expect(ended).toHaveBeenCalledWith(false)
  })

  it('tells the caller that a reading was replaced by another, and not the new one', () => {
    const speech = installSpeech(voices)
    const first = vi.fn()
    const second = vi.fn()
    speaker.speak('first', 'The first text here.', 'en', first)

    speaker.speak('second', 'The second text here.', 'en', second)

    expect(first).toHaveBeenCalledWith(false)
    expect(second).not.toHaveBeenCalled()
    speech.finishPiece()
    expect(second).toHaveBeenCalledWith(true)
  })

  it('tells the caller that a reading failed', () => {
    const speech = installSpeech(voices)
    const ended = vi.fn()
    speaker.speak('x', 'Some text here.', 'en', ended)

    speech.synthesis.cancel() // the browser reports an error to the utterance

    expect(ended).toHaveBeenCalledWith(false)
  })

  it('does not call back when there is no voice to read with', () => {
    installSpeech(voices)
    const ended = vi.fn()

    expect(speaker.speak('x', 'এটি একটি বাক্য।', 'bn', ended)).toBe(false)

    expect(ended).not.toHaveBeenCalled()
  })

  it('reads at the chosen speed and remembers it', () => {
    const speech = installSpeech(voices)

    speaker.setRate('slow')
    speaker.speak('x', 'Slowly now.', 'en')

    expect(speech.spoken()[0]?.rate).toBe(0.8)
    expect(localStorage.getItem('civicsaathi.speech-rate')).toBe('slow')
  })

  it('still reads when the browser will not store the speed', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const speech = installSpeech(voices)

    speaker.setRate('fast')
    speaker.speak('x', 'Quickly now.', 'en')

    expect(speech.spoken()[0]?.rate).toBe(1.25)
  })
})
