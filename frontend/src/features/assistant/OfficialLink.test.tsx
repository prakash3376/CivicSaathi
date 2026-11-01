import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { answerBody, citationBody } from '@/test/utils'
import { AnswerView } from './AnswerView'
import { isWebAddress } from './links'
import { OfficialLink } from './OfficialLink'
import { translator } from './strings'

const t = translator('en')

describe('isWebAddress', () => {
  it.each(['https://svmcm.wb.gov.in/a.pdf', 'http://example.gov.in/', 'HTTPS://EXAMPLE.GOV.IN'])(
    'accepts a web page: %s',
    (address) => {
      expect(isWebAddress(address)).toBe(true)
    },
  )

  it.each([
    'javascript:alert(1)',
    'JaVaScRiPt:alert(1)',
    ' javascript:alert(1)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    'ftp://example.gov.in/a.pdf',
    '/relative/path',
    'not an address',
    '',
  ])('refuses anything else: %j', (address) => {
    expect(isWebAddress(address)).toBe(false)
  })
})

describe('OfficialLink', () => {
  it('is a link that opens in a new tab and says so to a screen reader', () => {
    render(
      <OfficialLink
        url="https://svmcm.wb.gov.in/a.pdf"
        title="SVMCM Guidelines"
        openLabel={t('openDocument')}
      />,
    )

    const link = screen.getByRole('link')

    expect(link).toHaveAttribute('href', 'https://svmcm.wb.gov.in/a.pdf')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
    expect(link).toHaveAccessibleName('SVMCM Guidelines (opens the official document in a new tab)')
  })

  it('is plain text, not a link, for an address that could run a script', () => {
    render(
      <OfficialLink
        url="javascript:alert(document.cookie)"
        title="SVMCM Guidelines"
        openLabel={t('openDocument')}
      />,
    )

    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('SVMCM Guidelines')).toBeInTheDocument()
  })

  it('protects a citation whose record in the index has been tampered with', () => {
    const tampered = {
      ...answerBody,
      citations: [{ ...citationBody, url: 'javascript:alert(1)' }],
    }

    const { container } = render(<AnswerView answer={tampered} t={t} />)

    expect(container.querySelector('a[href^="javascript"]')).toBeNull()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText(citationBody.title)).toBeInTheDocument()
  })
})
