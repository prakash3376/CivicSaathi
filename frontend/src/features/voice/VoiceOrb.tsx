export type OrbMode = 'idle' | 'listening' | 'thinking' | 'speaking'

const BARS = [0, 0.15, 0.3, 0.15, 0] // the delay of each bar, so that they rise in a wave

const icon = {
  width: 40,
  height: 40,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

/**
 * The big round mark of the voice panel. What it shows says what is happening: a microphone with
 * rings spreading while listening, a spinner while looking up, bars rising while speaking. It is
 * only decoration (the button's words and the live region carry the meaning), and it stands still
 * for someone who asked their device for less motion.
 */
export function VoiceOrb({ mode }: { mode: OrbMode }) {
  return (
    <span aria-hidden="true" className="relative grid size-28 place-items-center">
      {mode === 'listening' &&
        [0, 0.9].map((delay) => (
          <span
            key={delay}
            style={{ animationDelay: `${delay}s` }}
            className="absolute inset-2 rounded-full border-2 border-brand opacity-40 motion-safe:animate-[voice-ring_1.8s_ease-out_infinite] motion-reduce:scale-125"
          />
        ))}
      <span className="relative grid size-24 place-items-center rounded-full bg-brand text-white shadow-lg">
        {(mode === 'idle' || mode === 'listening') && (
          <svg {...icon}>
            <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" />
            <path d="M19 11a7 7 0 0 1-14 0M12 18v3" />
          </svg>
        )}
        {mode === 'thinking' && (
          <svg
            {...icon}
            className="motion-safe:animate-[voice-spin_1s_linear_infinite]"
            strokeDasharray="42 20"
          >
            <circle cx="12" cy="12" r="9" />
          </svg>
        )}
        {mode === 'speaking' && (
          <span className="flex h-9 items-center gap-1.5">
            {BARS.map((delay, index) => (
              <span
                key={index}
                style={{ animationDelay: `${delay}s` }}
                className="h-full w-1.5 origin-center rounded-full bg-white motion-safe:animate-[voice-bar_0.9s_ease-in-out_infinite] motion-reduce:scale-y-75"
              />
            ))}
          </span>
        )}
      </span>
    </span>
  )
}
