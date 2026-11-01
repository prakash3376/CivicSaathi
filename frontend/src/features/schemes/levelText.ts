import type { Translate } from './strings'

/** Who runs a scheme, in words: the central government, or a state's. */
export function levelText(
  scheme: { level: 'central' | 'state'; state: string | null },
  t: Translate,
) {
  return scheme.level === 'state' && scheme.state
    ? t('levelState', { state: scheme.state })
    : t('levelCentral')
}
