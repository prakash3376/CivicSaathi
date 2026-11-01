import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { secondaryButton } from '@/components/ui/buttonStyles'
import { useSchemes } from '@/features/schemes/hooks'
import { isSectorId } from '@/features/sectors/sectors'
import { sectorTitle, useSectorText } from '@/features/sectors/useSectorText'
import { VoiceConversation } from '@/features/voice/VoiceConversation'
import { useLanguage } from '@/i18n/LanguageContext'
import { AskForm } from './AskForm'
import { ChatTurn } from './ChatTurn'
import { translator } from './strings'
import { useChat } from './useChat'
import { useLanguageChoice } from './useLanguageChoice'

const ALL = ''

/**
 * The part of the assistant's page that holds the conversation: the voice panel, the exchanges,
 * the choice of scheme and the question box. It owns the conversation, so the page puts a boundary
 * around it: if it ever fails to render, the rest of the page stays and this part starts again
 * with an empty conversation.
 */
export function ChatSection() {
  const { language: uiLanguage } = useLanguage()
  const t = useMemo(() => translator(uiLanguage), [uiLanguage])
  const [answerLanguage, setAnswerLanguage] = useLanguageChoice()
  const [search, setSearch] = useSearchParams()
  const schemes = useSchemes()
  const { t: sectorT } = useSectorText()
  const chat = useChat()

  const scheme = schemes.data?.find((candidate) => candidate.id === search.get('scheme'))
  // ?sector=health limits the answer to the documents behind that sector's programmes and budget.
  const wantedSector = search.get('sector')
  const sector = scheme || !isSectorId(wantedSector ?? undefined) ? undefined : wantedSector
  // A chosen scheme limits the answer to its documents. A sector only nudges the search.
  const scopeIds = scheme?.source_ids
  const hint = sector && isSectorId(sector) ? sector : undefined

  function chooseScope(id: string) {
    setSearch(id === ALL ? {} : { scheme: id }, { replace: true })
  }

  return (
    <>
      {/* Keyed by the language of the page: changing it ends a conversation in the old one. */}
      <VoiceConversation
        key={uiLanguage}
        uiLanguage={uiLanguage}
        answerChoice={answerLanguage}
        onAsk={chat.ask}
        sourceIds={scopeIds}
        sector={hint}
        busy={chat.pending}
      />

      {chat.turns.length > 0 && (
        <section aria-labelledby="conversation-heading" className="space-y-6">
          <h2 id="conversation-heading" className="sr-only">
            {t('conversation')}
          </h2>
          <ol className="space-y-8">
            {chat.turns.map((turn) => (
              <ChatTurn key={turn.id} turn={turn} t={t} onRetry={() => chat.retry(turn.id)} />
            ))}
          </ol>
          <button type="button" onClick={chat.clear} className={secondaryButton}>
            {t('newConversation')}
          </button>
        </section>
      )}

      <div className="space-y-4">
        {schemes.data && schemes.data.length > 0 && (
          <div className="space-y-2">
            <label htmlFor="scope" className="block font-medium">
              {t('scopeLabel')}
            </label>
            <select
              id="scope"
              value={scheme?.id ?? ALL}
              onChange={(event) => chooseScope(event.target.value)}
              className="min-h-12 w-full max-w-md rounded-xl border border-muted bg-surface px-3 text-ink"
            >
              <option value={ALL}>{t('scopeAll')}</option>
              {schemes.data.map((candidate) => (
                <option key={candidate.id} value={candidate.id}>
                  {candidate.name}
                </option>
              ))}
            </select>
            {scheme && (
              <p className="text-sm text-muted">{t('scopeNote', { scheme: scheme.name })}</p>
            )}
            {sector && isSectorId(sector) && (
              <p className="text-sm text-muted">
                {sectorT('scopeSector', { sector: sectorTitle(sectorT, sector) })}{' '}
                <button
                  type="button"
                  onClick={() => chooseScope(ALL)}
                  className="inline-flex min-h-12 items-center text-brand underline"
                >
                  {sectorT('scopeClear')}
                </button>
              </p>
            )}
          </div>
        )}

        <AskForm
          t={t}
          uiLanguage={uiLanguage}
          dictationLanguage={answerLanguage === 'auto' ? uiLanguage : answerLanguage}
          language={answerLanguage}
          onLanguageChange={setAnswerLanguage}
          onAsk={(question) =>
            chat.ask({
              question,
              language: answerLanguage,
              ...(scopeIds && scopeIds.length > 0 ? { source_ids: scopeIds } : {}),
              ...(hint ? { sector: hint } : {}),
            })
          }
          pending={chat.pending}
          showExamples={chat.turns.length === 0}
          initialQuestion={search.get('q') ?? ''}
        />
      </div>
    </>
  )
}
