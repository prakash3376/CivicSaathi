import { useLanguage } from '@/i18n/LanguageContext'
import { LANGUAGES, type UiLanguage } from '@/i18n/translator'

interface Props {
  label: string
  names: Record<UiLanguage, string>
}

const base = 'inline-flex min-h-12 min-w-12 items-center justify-center rounded-xl px-3 font-medium'

/** Two buttons, one per language; the pressed one is the language of the whole interface. */
export function LanguageSwitch({ label, names }: Props) {
  const { language, setLanguage } = useLanguage()
  return (
    <fieldset className="flex gap-1">
      <legend className="sr-only">{label}</legend>
      {LANGUAGES.map((code) => (
        <button
          key={code}
          type="button"
          lang={code}
          aria-pressed={language === code}
          onClick={() => setLanguage(code)}
          className={`${base} ${language === code ? 'bg-brand text-white' : 'text-brand hover:bg-brand-soft'}`}
        >
          {names[code]}
        </button>
      ))}
    </fieldset>
  )
}
