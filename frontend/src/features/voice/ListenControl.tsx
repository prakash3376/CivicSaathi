import { useEffect } from 'react'
import { secondaryButton } from '@/components/ui/buttonStyles'
import type { UiLanguage } from '@/i18n/translator'
import { useSpeaker, useVoiceAvailability, useVoiceText } from './hooks'
import { RATES, speaker, type RateName } from './speaker'
import { LANGUAGE_NAME, type VoiceKey } from './strings'

interface Props {
  /** Tells this reading from another, so that only the one being read shows "Stop". */
  id: string
  /** What to read: text the page already shows. */
  text: string
  /** The language of `text`; it is read only with a voice for that language. */
  language: UiLanguage
  /** What the button says when idle: "Listen to this answer". */
  label: VoiceKey
  /** The language of the interface, for the control's own words. */
  uiLanguage: UiLanguage
}

const RATE_LABEL: Record<RateName, VoiceKey> = {
  slow: 'speedSlow',
  normal: 'speedNormal',
  fast: 'speedFast',
}

/**
 * Reads `text` aloud, with a speed choice. If the device has no voice for the language the
 * person is told so and the text stays on the screen (SPEC rule R8): no silent failure, and no
 * English voice mangling Bengali.
 */
export function ListenControl({ id, text, language, label, uiLanguage }: Props) {
  const t = useVoiceText(uiLanguage)
  const availability = useVoiceAvailability(language)
  const { playingId, rate } = useSpeaker()
  const playing = playingId === id

  // Leaving the page, or this text being replaced, ends its reading.
  useEffect(
    () => () => {
      if (speaker.getSnapshot().playingId === id) speaker.stop()
    },
    [id],
  )

  if (availability === 'unsupported') {
    return <p className="text-sm text-muted">{t('noSynthesis')}</p>
  }
  if (availability === 'missing') {
    const name = t(LANGUAGE_NAME[language])
    return <p className="text-sm text-muted">{t('noVoice', { language: name })}</p>
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={() => (playing ? speaker.stop() : speaker.speak(id, text, language))}
        className={secondaryButton}
      >
        {t(playing ? 'stopReading' : label)}
      </button>
      <select
        aria-label={t('speed')}
        value={rate}
        onChange={(event) => speaker.setRate(event.target.value as RateName)}
        className="min-h-12 rounded-xl border border-muted bg-surface px-3 text-ink"
      >
        {(Object.keys(RATES) as RateName[]).map((name) => (
          <option key={name} value={name}>
            {t(RATE_LABEL[name])}
          </option>
        ))}
      </select>
    </div>
  )
}
