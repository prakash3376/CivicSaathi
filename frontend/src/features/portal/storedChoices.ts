/**
 * The only things the site keeps in the browser: the interface language, the answer language and
 * the reading speed. The keys are owned by the code that uses them (`LanguageProvider`,
 * `useLanguageChoice`, `speaker`); this module only shows what is stored and clears it.
 */
const KEYS = {
  interface: 'civicsaathi.ui-language',
  answer: 'civicsaathi.language',
  speed: 'civicsaathi.speech-rate',
} as const

export interface StoredChoices {
  interface: string | null
  answer: string | null
  speed: string | null
}

const NOTHING: StoredChoices = { interface: null, answer: null, speed: null }

function get(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null // storage can be blocked (a private window, strict settings)
  }
}

export function readChoices(): StoredChoices {
  return {
    interface: get(KEYS.interface),
    answer: get(KEYS.answer),
    speed: get(KEYS.speed),
  }
}

/** Forget every choice. Returns what is stored afterwards (nothing, unless storage is blocked). */
export function clearChoices(): StoredChoices {
  try {
    for (const key of Object.values(KEYS)) localStorage.removeItem(key)
  } catch {
    return readChoices()
  }
  return NOTHING
}
