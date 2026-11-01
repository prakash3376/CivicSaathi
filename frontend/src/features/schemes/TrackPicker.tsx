import { useId } from 'react'
import type { LocalText } from '@/api/types'
import { local, type UiLanguage } from '@/i18n/translator'

interface Track {
  id: string
  label: LocalText
  description?: LocalText | null
}

interface Props {
  legend: string
  tracks: Track[]
  value: string | null
  onChange: (id: string) => void
  language: UiLanguage
}

/** Choose one course or group. Each choice is a whole-row target of at least 48px. */
export function TrackPicker({ legend, tracks, value, onChange, language }: Props) {
  const name = useId()
  return (
    <fieldset className="space-y-2">
      <legend className="font-semibold">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2">
        {tracks.map((track) => (
          <label
            key={track.id}
            className="flex min-h-12 cursor-pointer items-start gap-3 rounded-xl border border-muted bg-surface p-3 has-[:checked]:border-brand has-[:checked]:bg-brand-soft"
          >
            <input
              type="radio"
              name={name}
              value={track.id}
              checked={value === track.id}
              onChange={() => onChange(track.id)}
              className="mt-1 size-5 accent-brand"
            />
            <span>
              <span className="block font-medium">{local(track.label, language)}</span>
              {track.description && (
                <span className="block text-sm text-muted">
                  {local(track.description, language)}
                </span>
              )}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
