import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatDate } from '@/features/assistant/dates'
import { renderAt } from '@/test/render'
import {
  eligibleBody,
  needMoreInfoBody,
  schemeDetailsBody,
  schemesBody,
} from '@/test/schemeFixtures'
import { answerBody, expectNoAxeViolations, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const CHECK = '/api/v1/schemes/svmcm/eligibility'
const ASK = '/api/v1/assistant/ask'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubAll(check = eligibleBody) {
  return stubApi({
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
    [CHECK]: () => jsonResponse(check),
    [ASK]: () => jsonResponse(answerBody),
  })
}

const hindi = () =>
  userEvent.click(within(screen.getAllByRole('banner')[0]!).getByRole('button', { name: 'हिन्दी' }))

describe('the switch', () => {
  it('offers English, Bengali and Hindi, each named in its own script', () => {
    stubAll()
    renderAt('/')

    const group = screen.getByRole('group', { name: 'Language' })

    expect(
      within(group)
        .getAllByRole('button')
        .map((b) => b.textContent),
    ).toEqual(['English', 'বাংলা', 'हिन्दी'])
    expect(within(group).getByRole('button', { name: 'हिन्दी' })).toHaveAttribute('lang', 'hi')
  })

  it('turns the frame and the home page into Hindi, marks the page as Hindi, and remembers it', async () => {
    stubAll()
    const { unmount } = renderAt('/')

    await hindi()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'सरकारी सेवाएँ, आसान भाषा में।',
    )
    expect(screen.getByRole('navigation', { name: 'मुख्य मेनू' })).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toHaveTextContent('कानूनी सलाह नहीं')
    expect(document.documentElement.lang).toBe('hi')
    expect(localStorage.getItem('civicsaathi.ui-language')).toBe('hi')
    unmount()
    renderAt('/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('आसान भाषा में')
  })

  it('starts in Hindi for a browser set to Hindi', () => {
    stubAll()
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('hi-IN')

    renderAt('/')

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('आसान भाषा में')
  })

  it('ignores a remembered language that is not one of ours', () => {
    stubAll()
    localStorage.setItem('civicsaathi.ui-language', 'ta')

    renderAt('/')

    expect(document.documentElement.lang).toBe('en')
  })

  it('has no automatically detectable accessibility problems in Hindi', async () => {
    stubAll()
    const { container } = renderAt('/')
    await hindi()

    await expectNoAxeViolations(container)
  })
})

describe('the schemes in Hindi', () => {
  it('shows what the schemes say in Hindi, with the date written in Hindi', async () => {
    stubAll()
    renderAt('/schemes')
    await screen.findAllByRole('article')

    await hindi()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('योजनाएँ खोजें')
    expect(
      screen.getByText('पश्चिम बंगाल के विद्यार्थियों के लिए वार्षिक छात्रवृत्ति।'),
    ).toBeVisible()
    const date = formatDate('2026-10-31', 'hi')
    expect(screen.getByText(`आवेदन की अंतिम तिथि: ${date} (अभी 11 दिन बाकी)`)).toBeVisible()
    expect(date).toMatch(/^31 .+ 2026$/) // digits 0-9, the month in Hindi
    expect(screen.getByText(/राज्य सरकार: West Bengal/)).toBeVisible()
  })

  it('shows a scheme in detail in Hindi, quotes still in their own language', async () => {
    stubAll()
    renderAt('/schemes/svmcm')
    await screen.findByRole('heading', { level: 1 })

    await hindi()

    expect(screen.getByText('1,000 रुपये प्रति माह, 10 माह तक।')).toBeVisible()
    const criteria = screen.getByRole('region', { name: 'कौन पा सकता है' })
    await userEvent.click(
      within(criteria).getAllByRole('button', { name: 'सरकारी दस्तावेज़ के शब्द देखें' })[0]!,
    )
    expect(
      within(criteria)
        .getByText(/not more than Rs. 2,50,000/)
        .closest('blockquote'),
    ).toHaveAttribute('lang', 'en')
  })
})

describe('the eligibility check in Hindi', () => {
  it('asks, reads Devanagari digits, and answers in Hindi', async () => {
    const fetchMock = stubAll(needMoreInfoBody)
    renderAt('/schemes/svmcm/check?track=ug')
    await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
    await hindi()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('अपनी पात्रता जाँचें')
    const income = screen.getByRole('textbox', { name: 'आपके परिवार की सालाना आय कितनी है?' })
    expect(screen.getByText('रुपये प्रति वर्ष')).toBeVisible()
    await userEvent.type(income, '\u{0969},\u{0966}\u{0966},\u{0966}\u{0966}\u{0966}')
    await userEvent.click(screen.getByRole('button', { name: 'जाँचें' }))

    const result = await screen.findByRole('region', { name: 'आपका परिणाम' })
    expect(within(result).getByText('हमें थोड़ी और जानकारी चाहिए')).toBeVisible()
    expect(
      within(result).getByText('पारिवारिक आय प्रति वर्ष अधिकतम 2,50,000 रुपये है'),
    ).toBeVisible()
    const body = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === CHECK)?.[1]?.body))
    expect(body.answers.family_income).toBe(300000)
  })

  it('shows yes, no and the way to skip in Hindi', async () => {
    stubAll()
    renderAt('/schemes/svmcm/check?track=ug')
    await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
    await hindi()

    const question = screen.getByRole('group', {
      name: 'क्या आपका कॉलेज या विश्वविद्यालय पश्चिम बंगाल में है?',
    })

    expect(
      within(question)
        .getAllByRole('radio')
        .map((r) => r.closest('label')?.textContent),
    ).toEqual(['हाँ', 'नहीं', 'पता नहीं'])
  })

  it('has no automatically detectable accessibility problems in Hindi, form and result', async () => {
    stubAll()
    const { container } = renderAt('/schemes/svmcm/check?track=ug')
    await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
    await hindi()
    await expectNoAxeViolations(container)

    await userEvent.click(screen.getByRole('button', { name: 'जाँचें' }))
    await screen.findByRole('heading', { level: 2, name: 'आपका परिणाम' })

    await expectNoAxeViolations(container)
  })
})

describe('the assistant in Hindi', () => {
  it('asks for a Hindi answer, offers Hindi examples, and keeps the page language apart', async () => {
    const fetchMock = stubAll()
    renderAt('/ask')
    await screen.findByRole('heading', { level: 1, name: 'Ask about a scholarship' })

    await userEvent.selectOptions(
      screen.getByRole('combobox', { name: 'Answer language' }),
      'हिन्दी',
    )
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Your question' }),
      'आय की सीमा क्या है?',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))
    await screen.findByRole('heading', { level: 2, name: 'Answer' })

    const sent = JSON.parse(String(fetchMock.mock.calls.find(([url]) => url === ASK)?.[1]?.body))
    expect(sent).toEqual({ question: 'आय की सीमा क्या है?', language: 'hi' })
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ask about a scholarship')
  })

  it('shows the page, the examples and the sources in Hindi', async () => {
    stubAll()
    renderAt('/ask')
    await hindi()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'छात्रवृत्ति के बारे में पूछें',
    )
    expect(screen.getByRole('textbox', { name: 'आपका प्रश्न' })).toBeVisible()
    expect(
      screen.getByRole('button', { name: 'आवेदन करने के लिए कौन-कौन से दस्तावेज़ चाहिए?' }),
    ).toBeVisible()
    expect(
      await screen.findByRole('region', { name: 'जिन दस्तावेज़ों से सहायक उत्तर देता है' }),
    ).toBeVisible()
  })

  it('reads the remembered answer language "hi"', async () => {
    stubAll()
    localStorage.setItem('civicsaathi.language', 'hi')

    renderAt('/ask')

    expect(await screen.findByRole('combobox', { name: 'Answer language' })).toHaveValue('hi')
  })

  it('has no automatically detectable accessibility problems in Hindi, with an answer', async () => {
    stubAll()
    const { container } = renderAt('/ask')
    await hindi()
    await userEvent.type(
      screen.getByRole('textbox', { name: 'आपका प्रश्न' }),
      'आय की सीमा क्या है?',
    )
    await userEvent.click(screen.getByRole('button', { name: 'पूछें' }))
    await screen.findByRole('heading', { level: 2, name: 'उत्तर' })

    await expectNoAxeViolations(container)
  })
})
