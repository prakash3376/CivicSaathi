import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { EligibilityResult } from '@/api/types'
import { renderAt } from '@/test/render'
import {
  eligibleBody,
  needMoreInfoBody,
  notEligibleBody,
  schemeDetailsBody,
  schemesBody,
  waivedBody,
} from '@/test/schemeFixtures'
import { expectNoAxeViolations, jsonResponse, sourcesBody, stubApi } from '@/test/utils'

const CHECK = '/api/v1/schemes/svmcm/eligibility'

beforeEach(() => {
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function stubCheck(reply: EligibilityResult | (() => Response) = eligibleBody) {
  return stubApi({
    '/api/v1/schemes': () => jsonResponse(schemesBody),
    '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
    '/api/v1/sources': () => jsonResponse(sourcesBody),
    [CHECK]: typeof reply === 'function' ? reply : () => jsonResponse(reply),
  })
}

async function openCheck(path = '/schemes/svmcm/check?track=ug') {
  const view = renderAt(path)
  await screen.findByRole('heading', { level: 1, name: 'Check your eligibility' })
  return view
}

const sent = (fetchMock: ReturnType<typeof stubCheck>) =>
  fetchMock.mock.calls
    .filter(([url]) => url === CHECK)
    .map(([, init]) => JSON.parse(String(init?.body)) as unknown)

/** The yes/no questions of the form (not the choice of course above it). */
const yesNoQuestions = () =>
  within(screen.getByRole('region', { name: 'About you' })).getAllByRole('group')

const submit = () => userEvent.click(screen.getByRole('button', { name: 'Check' }))

describe('choosing a course', () => {
  it('asks which course first when the address does not say, and shows no questions yet', async () => {
    stubCheck()
    await openCheck('/schemes/svmcm/check')

    expect(
      screen.getByRole('group', { name: /Which course or group are you applying for/ }),
    ).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Check' })).toBeNull()

    await userEvent.click(screen.getByRole('radio', { name: /Undergraduate/ }))

    expect(
      screen.getByRole('group', { name: 'Is your college or university in West Bengal?' }),
    ).toBeVisible()
  })

  it('starts at the course named in the address', async () => {
    stubCheck()
    await openCheck()

    expect(screen.getByRole('radio', { name: /Undergraduate/ })).toBeChecked()
    expect(
      screen.getByRole('textbox', { name: 'What is your family income in a year?' }),
    ).toBeVisible()
  })

  it('asks only the questions of the chosen course', async () => {
    stubCheck()
    await openCheck()
    expect(yesNoQuestions()).toHaveLength(2)

    await userEvent.click(screen.getByRole('radio', { name: /Postgraduate/ }))

    expect(
      screen.queryByRole('textbox', { name: 'What is your family income in a year?' }),
    ).toBeNull()
    expect(
      screen.getByRole('textbox', { name: 'What percentage of marks did you get?' }),
    ).toBeVisible()
  })

  it('forgets the answers and the result when the course changes', async () => {
    stubCheck()
    await openCheck()
    await userEvent.type(
      screen.getByRole('textbox', { name: 'What percentage of marks did you get?' }),
      '70',
    )
    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    await userEvent.click(screen.getByRole('radio', { name: /Postgraduate/ }))

    expect(screen.queryByRole('heading', { name: 'Your result' })).toBeNull()
    expect(
      screen.getByRole('textbox', { name: 'What percentage of marks did you get?' }),
    ).toHaveValue('')
  })

  it('treats an unknown course in the address as no choice', async () => {
    stubCheck()
    await openCheck('/schemes/svmcm/check?track=ghost')

    expect(screen.queryByRole('button', { name: 'Check' })).toBeNull()
    expect(screen.getByRole('radio', { name: /Undergraduate/ })).not.toBeChecked()
  })
})

describe('answering', () => {
  it('lets every question be skipped, and starts each yes/no question on "I don\'t know"', async () => {
    const fetchMock = stubCheck()
    await openCheck()

    for (const group of yesNoQuestions()) {
      expect(within(group).getByRole('radio', { name: "I don't know" })).toBeChecked()
    }
    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    expect(sent(fetchMock)).toEqual([{ track: 'ug', answers: {} }])
  })

  it('sends what was answered, as yes/no and numbers, and nothing else', async () => {
    const fetchMock = stubCheck()
    await openCheck()
    const inWestBengal = screen.getByRole('group', {
      name: 'Is your college or university in West Bengal?',
    })
    await userEvent.click(within(inWestBengal).getByRole('radio', { name: 'Yes' }))
    await userEvent.type(
      screen.getByRole('textbox', { name: 'What is your family income in a year?' }),
      '2,00,000',
    )
    const topper = screen.getByRole('group', {
      name: 'Did you rank among the toppers of your board?',
    })
    await userEvent.click(within(topper).getByRole('radio', { name: 'No' }))

    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    expect(sent(fetchMock)).toEqual([
      {
        track: 'ug',
        answers: { institution_in_west_bengal: true, family_income: 200000, board_topper: false },
      },
    ])
  })

  it('reads Bengali digits typed into a number box', async () => {
    const fetchMock = stubCheck()
    await openCheck()
    await userEvent.type(
      screen.getByRole('textbox', { name: 'What is your family income in a year?' }),
      '\u{09E8},\u{09E6}\u{09E6},\u{09E6}\u{09E6}\u{09E6}',
    )

    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    expect(sent(fetchMock)).toEqual([{ track: 'ug', answers: { family_income: 200000 } }])
  })

  it('shows hints and units with the question', async () => {
    stubCheck()
    await openCheck()

    const box = screen.getByRole('textbox', { name: 'What is your family income in a year?' })

    expect(box).toHaveAccessibleDescription('Add up the income of everyone in the family.')
    expect(screen.getByText('rupees a year')).toBeVisible()
  })

  it('refuses a number that cannot be used, says why next to it, and sends nothing', async () => {
    const fetchMock = stubCheck()
    await openCheck()
    const income = screen.getByRole('textbox', { name: 'What is your family income in a year?' })
    await userEvent.type(income, 'about two lakh')

    await submit()

    expect(income).toBeInvalid()
    expect(income).toHaveAccessibleDescription(/Please enter a number, using digits only\./)
    expect(income).toHaveFocus()
    expect(screen.getByRole('alert')).toHaveTextContent('Please correct the answers marked below.')
    expect(sent(fetchMock)).toEqual([])
  })

  it('names the limit when a number is out of range, and clears the message once it is fixed', async () => {
    const fetchMock = stubCheck()
    await openCheck()
    const marks = screen.getByRole('textbox', { name: 'What percentage of marks did you get?' })
    await userEvent.type(marks, '120')
    await submit()
    expect(marks).toHaveAccessibleDescription('The number cannot be more than 100.')

    await userEvent.clear(marks)
    await userEvent.type(marks, '80')

    expect(marks).toBeValid()
    expect(screen.queryByRole('alert')).toBeNull()
    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    expect(sent(fetchMock)).toEqual([{ track: 'ug', answers: { marks_percent: 80 } }])
  })

  it('announces the wait and keeps the button off until the result arrives', async () => {
    let release!: () => void
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    stubApi({
      '/api/v1/schemes': () => jsonResponse(schemesBody),
      '/api/v1/schemes/svmcm': () => jsonResponse(schemeDetailsBody),
      '/api/v1/sources': () => jsonResponse(sourcesBody),
      [CHECK]: async () => {
        await gate
        return jsonResponse(eligibleBody)
      },
    })
    await openCheck()

    await submit()

    expect(screen.getByRole('status')).toHaveTextContent('Checking the rules…')
    expect(screen.getByRole('button', { name: 'Check' })).toBeDisabled()
    release()
    const heading = await screen.findByRole('heading', { level: 2, name: 'Your result' })
    await waitFor(() => expect(heading).toHaveFocus())
  })
})

describe('the three results', () => {
  it('eligible: says so in words, with every rule met and the words behind each', async () => {
    stubCheck(eligibleBody)
    await openCheck()
    await submit()

    const result = await screen.findByRole('region', { name: 'Your result' })

    expect(
      within(result).getByRole('heading', {
        level: 3,
        name: 'You appear to meet every rule we checked',
      }),
    ).toBeVisible()
    const rules = within(result).getByRole('region', { name: 'The rules, one by one' })
    expect(within(rules).getAllByText('Met')).toHaveLength(2)
    expect(within(rules).getByText('Your answer: Rs 2,00,000 a year')).toBeVisible()
    expect(within(rules).getAllByRole('button', { name: 'Show the official words' })).toHaveLength(
      2,
    )
    expect(within(result).queryByText('Still needed')).toBeNull()
  })

  it('not eligible: says which rule is not met, and does not ask for what could not change it', async () => {
    stubCheck(notEligibleBody)
    await openCheck()
    await submit()

    const result = await screen.findByRole('region', { name: 'Your result' })

    expect(
      within(result).getByRole('heading', { level: 3, name: 'You do not meet at least one rule' }),
    ).toBeVisible()
    expect(within(result).getByText('Not met')).toBeVisible()
    expect(within(result).getByText('Not answered')).toBeVisible()
    expect(within(result).queryByText('Still needed')).toBeNull() // "marks_percent" is unanswered, but final
  })

  it('need more info: lists what is still needed and takes the reader to the first question', async () => {
    stubCheck(needMoreInfoBody)
    await openCheck()
    await submit()

    const result = await screen.findByRole('region', { name: 'Your result' })

    expect(
      within(result).getByRole('heading', { level: 3, name: 'We need a little more information' }),
    ).toBeVisible()
    const needed = within(result).getByText('Still needed').parentElement!
    expect(within(needed).getByText('What is your family income in a year?')).toBeVisible()

    await userEvent.click(within(needed).getByRole('button', { name: 'Answer these questions' }))

    expect(
      screen.getByRole('textbox', { name: 'What is your family income in a year?' }),
    ).toHaveFocus()
  })

  it('a rule that does not apply to the person is marked so, not as met', async () => {
    stubCheck(waivedBody)
    await openCheck()
    await submit()

    expect(await screen.findByText('Not required of you')).toBeVisible()
  })

  it('does not rely on color: every result and rule carries words', async () => {
    stubCheck(notEligibleBody)
    await openCheck()
    await submit()

    const result = await screen.findByRole('region', { name: 'Your result' })

    for (const icon of result.querySelectorAll('svg'))
      expect(icon).toHaveAttribute('aria-hidden', 'true')
  })

  it('is gone as soon as an answer is changed, so it never disagrees with the form', async () => {
    stubCheck(eligibleBody)
    await openCheck()
    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    await userEvent.type(
      screen.getByRole('textbox', { name: 'What percentage of marks did you get?' }),
      '5',
    )

    expect(screen.queryByRole('heading', { name: 'Your result' })).toBeNull()
  })
})

describe('the checklist', () => {
  it('separates documents needed from documents that may be needed, and counts the ones gathered', async () => {
    stubCheck(eligibleBody)
    await openCheck()
    await submit()
    const checklist = await screen.findByRole('region', { name: 'Your checklist' })

    expect(within(checklist).getByRole('list', { name: 'Documents you need' })).toHaveTextContent(
      'Bank account details',
    )
    expect(
      within(checklist).getByRole('list', { name: 'Documents you may need' }),
    ).toHaveTextContent('Proof of family income')
    expect(within(checklist).getByText('0 of 2 gathered')).toBeVisible()

    await userEvent.click(within(checklist).getByRole('checkbox', { name: /Bank account details/ }))

    expect(within(checklist).getByText('1 of 2 gathered')).toBeVisible()
    expect(within(checklist).getByRole('checkbox', { name: /Bank account details/ })).toBeChecked()
  })

  it('carries the steps, where to apply, whom to ask, and what the documents do not say', async () => {
    stubCheck(eligibleBody)
    await openCheck()
    await submit()
    await screen.findByRole('region', { name: 'Your checklist' })

    expect(screen.getAllByText('Apply online on the scholarship portal.').length).toBeGreaterThan(0)
    expect(
      screen.getAllByRole('link', { name: 'Email help@example.gov.in' }).length,
    ).toBeGreaterThan(0)
    expect(screen.getAllByText('Any fee for applying.').length).toBeGreaterThan(0)
  })

  it('ends with the disclaimer, in the language of the page', async () => {
    stubCheck(eligibleBody)
    await openCheck()
    await submit()

    expect(await screen.findByText(/Informational summary, not legal advice/)).toBeVisible()
  })
})

describe('when something goes wrong', () => {
  it('explains, quotes the reference, and tries the same answers again', async () => {
    const check = vi
      .fn()
      .mockImplementationOnce(() =>
        jsonResponse(
          {
            error: { code: 'schemes_unavailable', message: 'Not available.', request_id: 'req-9' },
          },
          { status: 503 },
        ),
      )
      .mockImplementation(() => jsonResponse(eligibleBody))
    const fetchMock = stubCheck(check)
    await openCheck()
    await userEvent.type(
      screen.getByRole('textbox', { name: 'What percentage of marks did you get?' }),
      '70',
    )

    await submit()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('We could not complete the check.')
    expect(alert).toHaveTextContent('Not available.')
    expect(alert).toHaveTextContent('Reference: req-9')
    await userEvent.click(within(alert).getByRole('button', { name: 'Try again' }))
    await screen.findByRole('heading', { level: 2, name: 'Your result' })
    const bodies = sent(fetchMock)
    expect(bodies).toHaveLength(2)
    expect(bodies[1]).toEqual(bodies[0])
  })

  it('says so when there is no such scheme', async () => {
    stubApi({
      '/api/v1/schemes/ghost': () =>
        jsonResponse({ error: { code: 'scheme_not_found', message: 'Nope.' } }, { status: 404 }),
    })
    renderAt('/schemes/ghost/check')

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Scheme not found')
  })
})

describe('privacy', () => {
  it('keeps answers out of the address and out of storage', async () => {
    stubCheck()
    const { router } = await openCheck()
    await userEvent.type(
      screen.getByRole('textbox', { name: 'What is your family income in a year?' }),
      '123457',
    )
    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    expect(router.state.location.search).toBe('?track=ug')
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain('123457')
    expect(Object.keys(localStorage).filter((key) => key !== 'civicsaathi.ui-language')).toEqual([])
    expect(
      screen.getByText('Your answers are used for this check only. They are not saved or shared.'),
    ).toBeVisible()
  })
})

describe('Bengali', () => {
  it('asks, answers and explains in Bengali, with figures in the digits 0-9', async () => {
    stubCheck(needMoreInfoBody)
    await openCheck()
    await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('আপনার যোগ্যতা যাচাই করুন')
    const income = screen.getByRole('textbox', { name: 'আপনার পরিবারের বার্ষিক আয় কত?' })
    expect(screen.getByText('টাকা প্রতি বছর')).toBeVisible()
    await userEvent.type(income, '9,00,000')
    await userEvent.click(screen.getByRole('button', { name: 'যাচাই করুন' }))

    const result = await screen.findByRole('region', { name: 'আপনার ফলাফল' })
    expect(within(result).getByText('আরও কিছু তথ্য দরকার')).toBeVisible()
    expect(within(result).getByText('পারিবারিক আয় বছরে সর্বোচ্চ 2,50,000 টাকা')).toBeVisible()
    expect(within(result).getAllByText('উত্তর দেওয়া হয়নি').length).toBeGreaterThan(0)
  })
})

describe('accessibility', () => {
  it('has no automatically detectable problems in the form, the three results and Bengali', async () => {
    for (const body of [eligibleBody, notEligibleBody, needMoreInfoBody, waivedBody]) {
      vi.unstubAllGlobals()
      stubCheck(body)
      const { container, unmount } = await openCheck()
      await expectNoAxeViolations(container)

      await submit()
      await screen.findByRole('heading', { level: 2, name: 'Your result' })
      await expectNoAxeViolations(container)

      await userEvent.click(screen.getByRole('button', { name: 'বাংলা' }))
      await expectNoAxeViolations(container)
      unmount()
      localStorage.clear()
    }
  })

  it('gives every control a touch target of at least 48 pixels', async () => {
    stubCheck(eligibleBody)
    await openCheck()
    await submit()
    await screen.findByRole('heading', { level: 2, name: 'Your result' })

    const controls = [
      ...screen.getAllByRole('button'),
      ...screen.getAllByRole('textbox'),
      ...screen.getAllByRole('radio').map((radio) => radio.closest('label')!),
      ...screen.getAllByRole('checkbox').map((box) => box.closest('label')!),
    ]

    for (const control of controls) expect(control.className, control.outerHTML).toMatch(/min-h-12/)
  })
})
