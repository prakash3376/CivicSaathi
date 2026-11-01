import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Answer, Citation } from '@/api/types'
import {
  answerBody,
  citationBody,
  expectNoAxeViolations,
  guidanceBody,
  notCoveredBody,
} from '@/test/utils'
import { AnswerView } from './AnswerView'
import { translator } from './strings'

function renderAnswer(answer: Answer = answerBody, language: 'en' | 'bn' = 'en') {
  return render(<AnswerView answer={answer} t={translator(language)} />)
}

const withCitation = (changes: Partial<Citation>): Answer => ({
  ...answerBody,
  citations: [{ ...citationBody, ...changes }],
})

describe('an answer', () => {
  it('shows each claim with a button for every source it rests on', () => {
    renderAnswer()

    expect(screen.getByRole('heading', { level: 2, name: 'Answer' })).toBeInTheDocument()
    expect(screen.getByText(answerBody.claims[0]!.text)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Source 1' })).toBeInTheDocument()
  })

  it('describes the source: where the words are, its date, and when it was last verified', () => {
    renderAnswer()

    expect(screen.getByText('Page 4 · MEANS JUDGING CRITERIA')).toBeInTheDocument()
    expect(screen.getByText('Dated 28 Apr 2026 · Last verified 31 Oct 2026')).toBeInTheDocument()
    expect(screen.getByText(citationBody.quote, { selector: 'blockquote' })).toBeInTheDocument()
  })

  it('links to the official document, in a new tab and without leaking the opener', () => {
    renderAnswer()

    const link = screen.getByRole('link', { name: /SVMCM Scholarship: Guidelines/ })

    expect(link).toHaveAttribute('href', citationBody.url)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(link).toHaveAccessibleName(/opens the official document in a new tab/)
  })

  it('keeps the original text out of the way until it is asked for', () => {
    renderAnswer()

    const toggle = screen.getByRole('button', { name: 'Show the original text' })

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(document.getElementById('source-1-text')).not.toBeVisible()
  })

  it('shows the passage with the quoted words highlighted, then hides it again', async () => {
    renderAnswer()

    await userEvent.click(screen.getByRole('button', { name: 'Show the original text' }))

    const passage = document.getElementById('source-1-text')!
    expect(passage).toBeVisible()
    expect(passage).toHaveTextContent('MEANS JUDGING CRITERIA')
    expect(within(passage).getByText(citationBody.quote).tagName).toBe('MARK')
    expect(screen.getByRole('button', { name: 'Hide the original text' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )

    await userEvent.click(screen.getByRole('button', { name: 'Hide the original text' }))

    expect(passage).not.toBeVisible()
  })

  it('opens the source and moves keyboard focus to it when a claim’s source button is pressed', async () => {
    renderAnswer()
    const button = screen.getByRole('button', { name: 'Source 1' })

    await userEvent.click(button)

    expect(document.getElementById('source-1-text')).toBeVisible()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    await waitFor(() => expect(document.getElementById('source-1')).toHaveFocus())
  })

  it('can be used from the keyboard alone', async () => {
    renderAnswer()
    const button = screen.getByRole('button', { name: 'Source 1' })
    button.focus()

    await userEvent.keyboard('{Enter}')

    expect(document.getElementById('source-1-text')).toBeVisible()
  })

  it('starts at its own heading, so a screen reader reads it from the top', () => {
    renderAnswer()

    expect(screen.getByRole('heading', { level: 2, name: 'Answer' })).toHaveFocus()
  })

  it('always shows the legal disclaimer', () => {
    renderAnswer()

    expect(screen.getByText(answerBody.disclaimer)).toBeInTheDocument()
  })
})

describe('what the answer says about its sources', () => {
  it('warns about a document more than twelve months old', () => {
    renderAnswer(withCitation({ stale: true }))

    expect(screen.getByText('More than 12 months old')).toBeInTheDocument()
  })

  it('warns that figures read from a scan may be wrong', () => {
    renderAnswer(withCitation({ ocr: true }))

    expect(screen.getByText('Read from a scan: check the figures')).toBeInTheDocument()
  })

  it('shows no vague "verified with warnings" badge: what matters has its own specific badge', () => {
    // Every real source passes its checks with warnings (an old date, a scan, a technical note
    // about TLS). The ones a reader can act on are named; a generic badge would only be noise.
    renderAnswer(withCitation({ verification: 'verified_with_warnings' }))

    expect(screen.queryByText(/warning/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('listitem', { name: /verified/i })).not.toBeInTheDocument()
  })

  it('shows no badge for a current, clean source', () => {
    renderAnswer()

    expect(screen.queryByText(/months old|scan|warnings/)).not.toBeInTheDocument()
  })

  it('says so when a document has no date or has never been verified', () => {
    renderAnswer(withCitation({ document_date: null, verified_at: null }))

    expect(screen.getByText('Date not found · Not verified yet')).toBeInTheDocument()
  })

  it('shows the notes the assistant attached, in their own section', () => {
    renderAnswer({
      ...answerBody,
      warnings: [
        {
          code: 'stale',
          message: 'SVMCM is dated 2024-01-01, more than 12 months ago.',
          source_ids: [],
        },
        { code: 'scanned', message: 'Read from a scanned copy.', source_ids: [] },
      ],
    })

    const notes = screen.getByRole('region', { name: 'Please note' })

    expect(within(notes).getAllByRole('listitem')).toHaveLength(2)
    expect(notes).toHaveTextContent('more than 12 months ago')
  })

  it('shows a page range, a web page, and a clause', () => {
    const { rerender } = renderAnswer(withCitation({ page_start: 3, page_end: 5, clause: '4.2' }))
    expect(
      screen.getByText('Pages 3 to 5 · MEANS JUDGING CRITERIA · Clause 4.2'),
    ).toBeInTheDocument()

    rerender(
      <AnswerView
        answer={withCitation({ page_start: null, page_end: null })}
        t={translator('en')}
      />,
    )
    expect(screen.getByText('Web page · MEANS JUDGING CRITERIA')).toBeInTheDocument()
  })
})

describe('an answer that is not an answer', () => {
  it('shows the message and no sources', () => {
    renderAnswer(notCoveredBody)

    expect(screen.getByText(/do not say this/)).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Sources for this answer' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Source/ })).not.toBeInTheDocument()
    expect(screen.getByText(notCoveredBody.disclaimer)).toBeInTheDocument()
  })

  it('lists the parts of the question that the documents do not cover', () => {
    renderAnswer({ ...notCoveredBody, not_stated: ['the monthly amount', 'the last date'] })

    const list = screen.getByRole('region', { name: 'The documents do not say' })

    expect(
      within(list)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['the monthly amount', 'the last date'])
  })
})

describe('languages', () => {
  const bengali: Answer = {
    ...answerBody,
    language: 'bn',
    claims: [
      { text: 'বৃত্তির জন্য পারিবারিক আয় 2,50,000 টাকার বেশি হতে পারবে না।', citations: [1] },
    ],
    disclaimer: 'এটি শুধুমাত্র তথ্যমূলক সারসংক্ষেপ, আইনি পরামর্শ নয়।',
  }

  it('marks the language of the answer, of the quote and of the labels around them', () => {
    const { container } = renderAnswer(bengali)

    expect(screen.getByText(bengali.claims[0]!.text)).toHaveAttribute('lang', 'bn')
    expect(screen.getByText(bengali.disclaimer)).toHaveAttribute('lang', 'bn')
    expect(screen.getByText(citationBody.quote, { selector: 'blockquote' })).toHaveAttribute(
      'lang',
      'en',
    )
    expect(container.querySelector('#source-1-text')).toHaveAttribute('lang', 'en')
  })

  it('can show the labels in Bengali around a Bengali answer', () => {
    renderAnswer(bengali, 'bn')

    expect(screen.getByRole('heading', { level: 2, name: 'উত্তর' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'উৎস 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'মূল লেখা দেখুন' })).toBeInTheDocument()
  })

  it('writes the dates of a source in Bengali on a Bengali page', () => {
    renderAnswer(bengali, 'bn')

    expect(
      screen.getByText('তারিখ 28 এপ্রিল, 2026 · সর্বশেষ যাচাই 31 অক্টোবর, 2026'),
    ).toBeInTheDocument()
  })
})

describe('accessibility', () => {
  it('has no automatically detectable problems, with everything open', async () => {
    const { container } = renderAnswer({
      ...answerBody,
      warnings: [
        { code: 'stale', message: 'An old document.', source_ids: ['wb-svmcm-guidelines'] },
      ],
      not_stated: ['the monthly amount'],
      citations: [
        { ...citationBody, stale: true, ocr: true, verification: 'verified_with_warnings' },
      ],
    })
    await userEvent.click(screen.getByRole('button', { name: 'Source 1' }))

    await expectNoAxeViolations(container)
  })

  it('has no automatically detectable problems when there is no answer', async () => {
    const { container } = renderAnswer(notCoveredBody)

    await expectNoAxeViolations(container)
  })

  it('makes every control at least 48 pixels tall', () => {
    renderAnswer()

    for (const button of screen.getAllByRole('button')) {
      expect(button.className).toMatch(/min-h-12/)
    }
  })
})

describe('general help', () => {
  it('says first that it is not from an official document, then helps, then asks', () => {
    const { container } = renderAnswer(guidanceBody)

    const wanted = [guidanceBody.guidance_intro, guidanceBody.text, guidanceBody.follow_up]
    const shown = Array.from(container.querySelectorAll('p'))
      .map((p) => p.textContent)
      .filter((text) => wanted.includes(text))
    expect(shown).toEqual(wanted)
  })

  it('has no sources and no source buttons: nothing here is quoted from a document', () => {
    renderAnswer(guidanceBody)

    expect(screen.queryByRole('button', { name: /Source/ })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { name: 'Sources for this answer' }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(guidanceBody.disclaimer)).toBeInTheDocument()
  })

  it('is accessible', async () => {
    const { container } = renderAnswer(guidanceBody)

    await expectNoAxeViolations(container)
  })
})
