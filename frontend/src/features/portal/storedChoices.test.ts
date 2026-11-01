import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearChoices, readChoices } from './storedChoices'

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('stored choices', () => {
  it('reads what the site keeps, and nothing else', () => {
    localStorage.setItem('civicsaathi.ui-language', 'bn')
    localStorage.setItem('civicsaathi.speech-rate', 'fast')
    localStorage.setItem('somebody-else', 'x')

    expect(readChoices()).toEqual({ interface: 'bn', answer: null, speed: 'fast' })
  })

  it('clears the three choices and leaves other things alone', () => {
    localStorage.setItem('civicsaathi.ui-language', 'bn')
    localStorage.setItem('civicsaathi.language', 'hi')
    localStorage.setItem('civicsaathi.speech-rate', 'fast')
    localStorage.setItem('somebody-else', 'x')

    expect(clearChoices()).toEqual({ interface: null, answer: null, speed: null })
    expect(localStorage.getItem('civicsaathi.ui-language')).toBeNull()
    expect(localStorage.getItem('somebody-else')).toBe('x')
  })

  it('reports nothing stored when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(readChoices()).toEqual({ interface: null, answer: null, speed: null })
  })

  it('still says what is stored when storage cannot be cleared', () => {
    localStorage.setItem('civicsaathi.ui-language', 'bn')
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(clearChoices().interface).toBe('bn')
  })
})
