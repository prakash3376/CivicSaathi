// A citizen's journey through the real application, in real Chrome: ten steps, with an accessibility
// check (axe, colour contrast included) on every page.
//
//   1  open the home page             6  ask the assistant (the model is made to fail)
//   2  open a sector                  7  see the sources of what came back
//   3  search within the sector       8  go to another sector (the budget)
//   4  open a scheme's details        9  switch the language
//   5  check eligibility             10  recover: try the question again
//
// It is not part of `npm test` and adds no dependency. To run it:
//
//   npm install --no-save puppeteer-core axe-core        (in a scratch folder, not the project)
//   node journey.mjs <web address of the app> [path to chrome]
//
// The app must be running with its API. Step 6 expects the language model to be unavailable (start
// the API with GEMINI_BASE_URL pointing at something that answers 503): that is what proves the
// visitor gets the matching official passages and a way to try again, not a blank error. With a
// working model the step passes if an answer or the passages appear.
import fs from 'node:fs'
import { createRequire } from 'node:module'
import puppeteer from 'puppeteer-core'

const require = createRequire(import.meta.url)
const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8')
const BASE = process.argv[2] ?? 'http://localhost:5173'
const CHROME = process.argv[3] ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const results = []
let page

async function step(name, run) {
  const started = Date.now()
  try {
    const detail = await run()
    results.push({ name, ok: true, ms: Date.now() - started, detail })
    console.log(`  ok    ${name} (${Date.now() - started} ms)${detail ? ': ' + detail : ''}`)
  } catch (error) {
    results.push({
      name,
      ok: false,
      ms: Date.now() - started,
      detail: String(error.message ?? error),
    })
    console.log(`  FAIL  ${name}: ${error.message ?? error}`)
  }
}

const expect = (condition, message) => {
  if (!condition) throw new Error(message)
}

async function text(selector) {
  return page.$eval(selector, (el) => el.textContent.trim())
}

async function waitText(selector, includes, timeout = 30_000) {
  await page.waitForFunction(
    (sel, wanted) => document.querySelector(sel)?.textContent.includes(wanted),
    { timeout },
    selector,
    includes,
  )
}

async function axeClean(label) {
  await page.evaluate(axeSource)
  const violations = await page.evaluate(async () =>
    (await window.axe.run(document)).violations.map((v) => `${v.id}: ${v.nodes.length}`),
  )
  expect(violations.length === 0, `${label}: accessibility problems: ${violations.join(', ')}`)
  return 'no accessibility violations'
}

async function clickByText(selector, wanted) {
  const found = await page.evaluateHandle(
    (sel, text) => [...document.querySelectorAll(sel)].find((el) => el.textContent.includes(text)),
    selector,
    wanted,
  )
  const element = found.asElement()
  expect(element, `nothing matching ${selector} contains "${wanted}"`)
  await element.click()
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox'],
})
const errors = []
try {
  page = await browser.newPage()
  await page.setViewport({ width: 1100, height: 900 })
  await page.evaluateOnNewDocument(() => localStorage.setItem('civicsaathi.ui-language', 'en'))
  page.on('pageerror', (e) => errors.push(e.message))
  page.on(
    'console',
    (m) =>
      m.type() === 'error' && !/Failed to load resource/.test(m.text()) && errors.push(m.text()),
  )

  await step('1. open the home page', async () => {
    await page.goto(BASE, { waitUntil: 'networkidle0' })
    expect(
      (await text('h1')).includes('Government services'),
      'the heading is not the home heading',
    )
    const sectors = await page.$$eval('a[href^="/sectors/"]', (links) => links.length)
    expect(sectors === 12, `${sectors} sector cards, not 12`)
    return `${sectors} sectors; ` + (await axeClean('home'))
  })

  await step('2. open a sector (Healthcare)', async () => {
    await clickByText('a[href^="/sectors/"]', 'Healthcare')
    await page.waitForFunction(() => location.pathname === '/sectors/health')
    await waitText('h1', 'Healthcare')
    await page.waitForSelector('article')
    const cards = await page.$$eval('main section article', (a) => a.length)
    expect(cards >= 3, `only ${cards} cards in Healthcare`)
    return `${cards} cards; ` + (await axeClean('sector'))
  })

  await step('3. search within the sector', async () => {
    await page.type('input[type=search]', 'health cover')
    await sleep(300)
    const shown = await page.$eval('main output', (o) => o.textContent)
    expect(/Showing \d+ scheme/.test(shown), `no result count: ${shown}`)
    const names = await page.$$eval('main section article h2', (h) => h.map((x) => x.textContent))
    expect(
      names.some((n) => /Swasthya|Ayushman/i.test(n)),
      `health cover schemes missing: ${names}`,
    )
    return shown
  })

  await step("4. open a scheme's details", async () => {
    await clickByText('article a', 'See details')
    await page.waitForFunction(() => location.pathname.startsWith('/schemes/'))
    await waitText('main', 'What you get')
    const quotes = await page.$$eval('button[aria-expanded]', (b) => b.length)
    expect(quotes > 0, 'no way to open the official words')
    return (await text('h1')) + '; ' + (await axeClean('details'))
  })

  await step(
    '5. check eligibility (skipping every question must never say "eligible")',
    async () => {
      await page.goto(`${BASE}/schemes/svmcm/check`, { waitUntil: 'networkidle0' })
      // The scheme has several courses: choose the first, as a person would, to reach the questions.
      await page.waitForSelector('input[type=radio]')
      await page.click('input[type=radio]')
      await page.waitForSelector('button[type=submit]')
      await clickByText('button[type=submit]', 'Check')
      await waitText('main', 'more', 20_000)
      const body = await text('main')
      expect(!/appear to meet every rule/i.test(body), 'a skipped check was called eligible')
      return 'need more information; ' + (await axeClean('eligibility'))
    },
  )

  await step('6. ask the assistant (the model is made to fail)', async () => {
    await page.goto(
      `${BASE}/ask?sector=agriculture&q=${encodeURIComponent('Who can get farmer money from the government?')}`,
      {
        waitUntil: 'networkidle0',
      },
    )
    await page.click('button[type=submit]')
    await page.waitForFunction(
      () => document.querySelector('main ol li h2, main ol li [role=alert]'),
      { timeout: 90_000 },
    )
    const body = await text('main ol')
    const fallback = /not answering right now/i.test(body)
    const answered = !fallback && !/not available|could not/i.test(body)
    expect(
      fallback || answered,
      `neither an answer nor the passages appeared: ${body.slice(0, 160)}`,
    )
    return fallback ? 'the model failed; the matching passages were shown' : 'answered'
  })

  await step('7. see the sources of what came back', async () => {
    const links = await page.$$eval('main ol a[href^="http"]', (a) => a.map((x) => x.href))
    expect(links.length > 0, 'no source links')
    expect(
      links.every((href) => href.startsWith('https://')),
      'a source link is not https',
    )
    const where = await text('main ol')
    expect(/page|web page/i.test(where), 'no page or place is given for a source')
    return `${links.length} source link(s), all https; ` + (await axeClean('answer'))
  })

  await step('8. go to another sector (Budget & Economy)', async () => {
    await page.goto(`${BASE}/sectors/budget`, { waitUntil: 'networkidle0' })
    await waitText('main', 'Budget Estimate')
    const body = await text('main')
    expect(
      /not money already spent|Actual spending/i.test(body),
      'the plan-versus-spending distinction is missing',
    )
    return (
      (await page.$$eval('main article', (a) => a.length)) +
      ' budget records; ' +
      (await axeClean('budget'))
    )
  })

  await step('9. switch the language to Hindi', async () => {
    await clickByText('header button', 'हिन्दी')
    await sleep(300)
    const lang = await page.evaluate(() => document.documentElement.lang)
    expect(lang === 'hi', `the page is marked '${lang}'`)
    expect(/[\u0900-\u097F]/.test(await text('h1')), 'the heading is not Devanagari')
    return 'html lang=hi; ' + (await axeClean('hindi'))
  })

  await step('10. recover: ask again after the failure', async () => {
    await page.goto(`${BASE}/ask?q=${encodeURIComponent('Who can apply for PMAY?')}`, {
      waitUntil: 'networkidle0',
    })
    await page.click('button[type=submit]')
    await page.waitForFunction(
      () => document.querySelector('main ol li h2, main ol li [role=alert]'),
      {
        timeout: 90_000,
      },
    )
    const retry = await page.evaluate(() =>
      [...document.querySelectorAll('main ol button')].some((b) =>
        /try again|আবার|फिर/i.test(b.textContent),
      ),
    )
    const ok = await page.evaluate(
      () => document.querySelectorAll('main ol a[href^="http"]').length > 0,
    )
    expect(retry || ok, 'neither a way to try again nor an answer')
    return retry ? 'a "Try again" button is offered' : 'answered'
  })

  await step('no script errors in the console', async () => {
    expect(errors.length === 0, errors.join(' | '))
  })
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length} of ${results.length} steps passed`)
process.exit(failed.length ? 1 : 0)
