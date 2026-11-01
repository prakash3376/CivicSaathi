import { useCallback, useState } from 'react'
import { secondaryButton } from '@/components/ui/buttonStyles'
import type { UiLanguage } from '@/i18n/translator'
import { useDictation, useVoiceText } from './hooks'
import { PROBLEM_TEXT } from './problems'
import { LANGUAGE_NAME } from './strings'

interface Props {
  /** The language the person will speak. */
  language: UiLanguage
  onStart: () => void
  /** The words recognised so far, as they grow. */
  onText: (text: string) => void
  /** Recognition ended; the question box should take focus so the words can be checked. */
  onFinish: (heard: boolean) => void
  /** The language of the interface, for the control's own words. */
  uiLanguage: UiLanguage
  disabled?: boolean
}

/**
 * A microphone for speaking a question. The recognised words go into the question box to be
 * checked and edited; nothing is sent until the person presses Ask. Says where the audio goes.
 */
export function MicButton({
  language,
  onStart,
  onText,
  onFinish,
  uiLanguage: ui,
  disabled = false,
}: Props) {
  const t = useVoiceText(ui)
  const finished = useFinish(onFinish)
  const dictation = useDictation(language, { onText, onFinish: finished.handle })

  if (!dictation.supported) {
    return <p className="text-sm text-muted">{t('micUnsupported')}</p>
  }

  const name = t(LANGUAGE_NAME[language])
  let status: string | null = null
  if (dictation.listening) status = t('micListening')
  else if (dictation.problem) {
    status = t(PROBLEM_TEXT[dictation.problem], { language: name })
  } else if (finished.heard) status = t('micHeard')

  return (
    <div className="space-y-2">
      <button
        type="button"
        disabled={disabled && !dictation.listening}
        onClick={() => {
          if (dictation.listening) dictation.stop()
          else {
            finished.reset()
            onStart()
            dictation.start()
          }
        }}
        className={secondaryButton}
      >
        {t(dictation.listening ? 'micStop' : 'mic')}
      </button>
      {/* <output> is a polite live region: "Listening…" and the problems are announced. */}
      <output
        lang={ui}
        className={`block ${dictation.problem ? 'font-medium text-danger' : 'text-muted'}`}
      >
        {status}
      </output>
      <p lang={ui} className="max-w-prose text-sm text-muted">
        {t('micPrivacy')}
      </p>
    </div>
  )
}

/** Remembers whether the last dictation heard anything, and passes the end on to the form. */
function useFinish(onFinish: (heard: boolean) => void) {
  const [heard, setHeard] = useState(false)
  const handle = useCallback(
    (didHear: boolean) => {
      setHeard(didHear)
      onFinish(didHear)
    },
    [onFinish],
  )
  return { heard, handle, reset: () => setHeard(false) }
}
