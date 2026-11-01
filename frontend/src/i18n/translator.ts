import type { LocalText } from '@/api/types'

/** The languages of the interface. Figures are always written with the digits 0-9. */
export type UiLanguage = 'en' | 'bn' | 'hi'

/** Every language, in the order the switch shows them. */
export const LANGUAGES: readonly UiLanguage[] = ['en', 'bn', 'hi']

export type Fields = Record<string, string | number>

/** Looks up a string and fills in its `{placeholders}`. */
export type TranslateWith<Key extends string> = ((key: Key, fields?: Fields) => string) & {
  /** The language the strings are in, so that dates can be written to match. */
  readonly language: UiLanguage
}

/** Make a `translator(language)` for one table of strings. */
export function createTranslator<Key extends string>(
  strings: Record<UiLanguage, Record<Key, string>>,
): (language: UiLanguage) => TranslateWith<Key> {
  return (language) => {
    const table = strings[language]
    const translate = (key: Key, fields: Fields = {}) =>
      table[key].replace(/\{(\w+)\}/g, (_match, name: string) =>
        String(fields[name] ?? `{${name}}`),
      )
    return Object.assign(translate, { language })
  }
}

/** The wording in the chosen language. */
export function local(text: LocalText, language: UiLanguage): string {
  return text[language]
}
