/** Primary call-to-action. `min-h-12` keeps the touch target at 48px or taller (WCAG 2.5.8). */
export const primaryButton =
  'inline-flex min-h-12 items-center justify-center rounded-xl bg-brand px-5 font-medium text-white ' +
  'hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-60'

/** A quieter action beside a primary one. The edge is `muted`, not `line`, so it shows (3:1). */
export const secondaryButton =
  'inline-flex min-h-12 items-center justify-center rounded-xl border border-muted bg-surface px-5 ' +
  'font-medium text-ink hover:bg-brand-soft disabled:cursor-not-allowed disabled:opacity-60'
