import { useMutation } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { fetchKnowledge, type KnowledgeReport } from '@/api/admin'
import { ApiError } from '@/api/client'
import { primaryButton } from '@/components/ui/buttonStyles'

const WORDS: Record<string, string> = {
  populated: 'Populated',
  incomplete: 'Incomplete',
  empty: 'Empty',
}

const number = new Intl.NumberFormat('en-IN')

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-2xl font-semibold">{value}</dd>
    </div>
  )
}

function Report({ report }: { report: KnowledgeReport }) {
  const { totals, assistant } = report
  return (
    <div className="space-y-8">
      <section aria-labelledby="totals" className="space-y-3">
        <h2 id="totals" className="text-xl font-bold">
          The documents
        </h2>
        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label="Indexed documents"
            value={`${totals.indexed_sources} of ${totals.registered_sources}`}
          />
          <Stat label="Verified documents" value={number.format(totals.verified_sources)} />
          <Stat label="Searchable passages" value={number.format(totals.passages)} />
          <Stat label="Embedded passages" value={number.format(totals.embedded_passages)} />
        </dl>
        <p className="text-sm text-muted">Last verified: {totals.last_verified_at ?? 'never'}</p>
      </section>

      <section aria-labelledby="sectors" className="space-y-3">
        <h2 id="sectors" className="text-xl font-bold">
          Sector by sector
        </h2>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[44rem] text-left">
            <caption className="sr-only">Records, documents and passages in each sector</caption>
            <thead className="bg-brand-soft text-sm">
              <tr>
                {[
                  'Sector',
                  'Status',
                  'Schemes',
                  'Programmes',
                  'Budget',
                  'Documents',
                  'Passages',
                  'Old',
                  'Due',
                ].map((head) => (
                  <th key={head} scope="col" className="px-3 py-2 font-semibold">
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.sectors.map((row) => (
                <tr key={row.sector} className="border-t border-line">
                  <th scope="row" className="px-3 py-2 font-medium">
                    {row.sector}
                  </th>
                  <td
                    className={`px-3 py-2 ${row.status === 'populated' ? '' : 'font-semibold text-danger'}`}
                  >
                    {WORDS[row.status]}
                  </td>
                  <td className="px-3 py-2">{row.schemes}</td>
                  <td className="px-3 py-2">{row.programmes}</td>
                  <td className="px-3 py-2">{row.budget_records}</td>
                  <td className="px-3 py-2">
                    {row.indexed_sources}/{row.sources}
                  </td>
                  <td className="px-3 py-2">{number.format(row.passages)}</td>
                  <td className="px-3 py-2">{row.stale_sources}</td>
                  <td className="px-3 py-2">{row.due_sources}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted">
          A passage count is shared by sectors that use the same document. Old: more than 12 months.
          Due: needs a new check.
        </p>
      </section>

      <section aria-labelledby="attention" className="space-y-3">
        <h2 id="attention" className="text-xl font-bold">
          Needs attention
        </h2>
        <p>
          <strong>Not indexed:</strong>{' '}
          {report.failed_ingestion.length > 0 ? report.failed_ingestion.join(', ') : 'none'}
        </p>
        <p>
          <strong>Due for a new check:</strong>{' '}
          {report.needs_new_check.length > 0 ? report.needs_new_check.join(', ') : 'none'}
        </p>
      </section>

      <section aria-labelledby="assistant" className="space-y-3">
        <h2 id="assistant" className="text-xl font-bold">
          The assistant since the server started
        </h2>
        <p>
          Language model: {report.provider.model}{' '}
          {report.provider.configured ? '(key set)' : '(no key set)'}
        </p>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Stat label="Questions" value={String(assistant.questions)} />
          <Stat
            label="Mean time"
            value={assistant.mean_ms === null ? '-' : `${assistant.mean_ms} ms`}
          />
          <Stat
            label="Slowest 5%"
            value={assistant.p95_ms === null ? '-' : `${assistant.p95_ms} ms`}
          />
        </dl>
        <p>
          Outcomes:{' '}
          {Object.entries(assistant.outcomes)
            .map(([name, count]) => `${name} ${count}`)
            .join(', ') || 'none yet'}
        </p>
        {assistant.recent_failures.length > 0 && (
          <ul className="list-disc pl-5">
            {assistant.recent_failures.map((failure) => (
              <li key={`${failure.at}${failure.code}`}>
                {failure.at}: {failure.code}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="evaluations" className="space-y-3">
        <h2 id="evaluations" className="text-xl font-bold">
          Latest benchmark runs
        </h2>
        {Object.keys(report.evaluations).length === 0 ? (
          <p className="text-muted">None yet. Run `python -m app.cli eval` in the backend.</p>
        ) : (
          <ul className="space-y-2">
            {Object.entries(report.evaluations).map(([name, run]) => (
              <li key={name} className="rounded-xl border border-line bg-surface p-4">
                <strong>{name}</strong> ({run.at ?? 'undated'}):{' '}
                {run.retrieval
                  ? Object.entries(run.retrieval)
                      .map(([key, value]) => `${key} ${value}`)
                      .join(', ')
                  : 'no retrieval figures'}
                {run.intent_accuracy !== null && `, intent accuracy ${run.intent_accuracy}`}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/**
 * The knowledge-base health page for whoever runs the site. It is not linked from the public
 * pages and needs the admin token, which is held in memory and sent as a header; the server has
 * the last word (no `ADMIN_TOKEN` there means the page does not exist). English only: it is an
 * operator's tool.
 */
export function AdminPage() {
  const id = useId()
  const [token, setToken] = useState('')
  const query = useMutation({ mutationFn: (value: string) => fetchKnowledge(value) })

  function submit(event: FormEvent) {
    event.preventDefault()
    if (token.trim()) query.mutate(token.trim())
  }

  const denied = query.error instanceof ApiError && query.error.status === 401
  const off = query.error instanceof ApiError && query.error.status === 404

  return (
    <div lang="en" className="space-y-8">
      <title>Knowledge base health · CivicSaathi</title>
      <section className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Knowledge base health</h1>
        <p className="max-w-prose text-muted">
          What each sector has, counted from the data and the index. For whoever runs the site.
        </p>
      </section>

      <form onSubmit={submit} className="max-w-md space-y-3">
        <label htmlFor={`${id}-token`} className="block font-medium">
          Admin token
        </label>
        <input
          id={`${id}-token`}
          type="password"
          autoComplete="off"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          className="min-h-12 w-full rounded-xl border border-muted bg-surface px-3 text-ink"
        />
        <button type="submit" disabled={query.isPending || !token.trim()} className={primaryButton}>
          {query.isPending ? 'Loading…' : 'Show the report'}
        </button>
        {denied && (
          <p role="alert" className="font-medium text-danger">
            The token is wrong.
          </p>
        )}
        {off && (
          <p role="alert" className="font-medium text-danger">
            This page is switched off: the server has no ADMIN_TOKEN.
          </p>
        )}
        {query.isError && !denied && !off && (
          <p role="alert" className="font-medium text-danger">
            The report could not be loaded.
          </p>
        )}
      </form>

      {query.isSuccess && <Report report={query.data} />}
    </div>
  )
}
