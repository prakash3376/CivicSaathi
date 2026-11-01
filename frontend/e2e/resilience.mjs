// What a citizen meets when things go wrong, in real Chrome: no connection, a slow connection, a page
// reloaded while a question is on its way, a button pressed twice. Each step checks that the
// application recovered, not only that it said something.
//
//   1  open a sector                          6  slow network: the page still arrives
//   2  go offline: the notice appears         7  reload while a question is waiting
//   3  open an unvisited page offline         8  press Ask twice: one request
//   4  that failure page is accessible        9  no unexpected script errors
//   5  back online, Try again: the page loads
//
// It is not part of `npm test` and adds no dependency. To run it:
//
//   npm install --no-save puppeteer-core axe-core        (in a scratch folder, not the project)
//   node resilience.mjs <web address of the app> [path to chrome]
//
// The app must be running with its API. The assistant steps expect the language model to be
// unavailable (start the API with GEMINI_BASE_URL pointing at something that answers 503): the
// question then ends quickly with the matching passages, which is all these steps need.
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
let client // the DevTools session, for network conditions

async function step(name, run) {
  const started = Date.now()
  try {
    const detail = await run()
    results.push({ name, ok: true, ms: Date.now() - started, detail })
    console.log(`  PASS  ${name} (${Date.now() - started} ms)${detail ? ': ' + detail : ''}`)
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

const text = (selector) => page.$eval(selector, (el) => el.textContent.trim())

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
    (sel, wantedText) =>
      [...document.querySelectorAll(sel)].find((el) => el.textContent.includes(wantedText)),
    selector,
    wanted,
  )
  const element = found.asElement()
  expect(element, `nothing matching ${selector} contains "${wanted}"`)
  await element.click()
}

async function network(conditions) {
  await client.send('Network.emulateNetworkConditions', conditions)
}
const ONLINE = { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 }

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox'],
})
// Errors the browser reports while the connection is deliberately broken are expected; the others are not.
const unexpected = []
let expectingFailures = false
try {
  page = await browser.newPage()
  client = await page.createCDPSession()
  await client.send('Network.enable')
  await page.setViewport({ width: 1100, height: 900 })
  await page.evaluateOnNewDocument(() => localStorage.setItem('civicsaathi.ui-language', 'en'))
  page.on('pageerror', (e) => !expectingFailures && unexpected.push(`pageerror: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() !== 'error' || expectingFailures) return
    if (/Failed to load resource/.test(m.text())) return
    unexpected.push(`console: ${m.text()}`)
  })
  const askRequests = []
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/api/v1/assistant/ask')) {
      askRequests.push(request.url())
    }
  })

  await step('1. open a sector', async () => {
    await page.goto(`${BASE}/sectors/agriculture`, { waitUntil: 'networkidle0' })
    await page.waitForSelector('h1')
    expect((await text('h1')).includes('Agriculture'), 'not the agriculture page')
    const notice = await page.evaluate(() =>
      [...document.querySelectorAll('output')].some((o) =>
        o.textContent.includes('You are offline'),
      ),
    )
    expect(!notice, 'an offline notice is shown while online')
    return 'agriculture page, no offline notice'
  })

  await step('2. go offline: the notice appears, and the page stays readable', async () => {
    expectingFailures = true
    await network({ ...ONLINE, offline: true })
    await page.waitForFunction(
      () =>
        [...document.querySelectorAll('output')].some((o) =>
          o.textContent.includes('You are offline'),
        ),
      { timeout: 10_000 },
    )
    const body = await page.$eval('output', (o) => o.textContent)
    expect(/out of date/.test(body), `the notice does not say the page may be out of date: ${body}`)
    expect(
      (await text('h1')).includes('Agriculture'),
      'the page on screen was lost when going offline',
    )
    return 'notice shown; the sector page is still on screen'
  })

  await step(
    '3. open a page that was never loaded: an explanation, not a blank screen',
    async () => {
      await clickByText('header nav a', 'Ask AI Saathi')
      await page.waitForSelector('[role=alert] h1', { timeout: 30_000 })
      const heading = await text('[role=alert] h1')
      expect(/could not be shown/.test(heading), `unexpected heading: ${heading}`)
      const alertText = await text('[role=alert]')
      expect(
        /Check your connection/.test(alertText),
        `the message does not point to the connection: ${alertText}`,
      )
      expect(!/dynamically imported|https?:\/\//.test(alertText), 'a raw browser error is shown')
      const headerLinks = await page.$$eval('header a', (links) => links.length)
      expect(headerLinks > 0, 'the header is gone')
      const focused = await page.evaluate(() => document.activeElement?.tagName)
      expect(focused === 'H1', `focus is on ${focused}, not the heading`)
      const buttons = await page.$$eval('[role=alert] button', (b) =>
        b.map((x) => x.textContent.trim()),
      )
      expect(buttons.includes('Try again'), 'no Try again button')
      return 'heading, plain message, header kept, focus on the heading, Try again offered'
    },
  )

  await step('4. the failure page is accessible', async () => axeClean('failure page'))

  await step('5. back online, Try again: the page loads', async () => {
    await network(ONLINE)
    await page.waitForFunction(
      () =>
        ![...document.querySelectorAll('output')].some((o) =>
          o.textContent.includes('You are offline'),
        ),
      { timeout: 10_000 },
    )
    expectingFailures = false
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'networkidle0' }),
      clickByText('[role=alert] button', 'Try again'),
    ])
    await page.waitForSelector('textarea')
    expect(!(await page.$('[role=alert] h1')), 'the failure page is still shown')
    expect(
      /Ask about/.test(await text('h1')),
      `unexpected heading on the recovered page: ${await text('h1')}`,
    )
    return `recovered on ${new URL(page.url()).pathname}`
  })

  await step('6. slow network: the page still arrives', async () => {
    await network({
      offline: false,
      latency: 300,
      downloadThroughput: 150 * 1024,
      uploadThroughput: 75 * 1024,
    })
    const started = Date.now()
    try {
      await page.goto(`${BASE}/sectors/health`, { waitUntil: 'load', timeout: 120_000 })
      await page.waitForSelector('main h1', { timeout: 120_000 })
      await page.waitForSelector('article', { timeout: 120_000 })
    } finally {
      await network(ONLINE)
    }
    const seconds = Math.round((Date.now() - started) / 1000)
    expect(!(await page.$('[role=alert] h1')), 'a failure page appeared on a slow connection')
    return `Healthcare page with its cards after ${seconds} s at 300 ms latency and 150 KB/s`
  })

  await step('7. reload while a question is waiting: the page is usable again', async () => {
    await page.goto(`${BASE}/ask`, { waitUntil: 'networkidle0' })
    await page.type('textarea', 'Who can get farmer money from the government?')
    const before = askRequests.length
    await page.click('button[type=submit]')
    await page.waitForFunction(() => document.querySelector('main ol li'), { timeout: 10_000 })
    await page.reload({ waitUntil: 'networkidle0' })
    await page.waitForSelector('textarea')
    expect(!(await page.$('[role=alert]')), 'an error is shown after reloading')
    expect(!(await page.$('main ol li')), 'the old conversation came back (it must not be stored)')
    await page.type('textarea', 'Who can apply for PMAY?')
    const value = await page.$eval('textarea', (t) => t.value)
    expect(value === 'Who can apply for PMAY?', 'the question box does not accept typing')
    const enabled = await page.$eval('button[type=submit]', (b) => !b.disabled)
    expect(enabled, 'the Ask button is stuck disabled after the reload')
    return `${askRequests.length - before} request before the reload; box and button work afterwards`
  })

  await step('8. press Ask twice: one request', async () => {
    await page.goto(`${BASE}/ask`, { waitUntil: 'networkidle0' })
    await page.type('textarea', 'What is the PM-KISAN amount?')
    const before = askRequests.length
    await page.click('button[type=submit]', { count: 2, delay: 10 })
    await sleep(2500)
    const sent = askRequests.length - before
    expect(sent === 1, `${sent} requests were sent`)
    await page.waitForFunction(
      () => document.querySelector('main ol li h2, main ol li [role=alert]'),
      { timeout: 90_000 },
    )
    const questions = await page.$$eval(
      'section[aria-labelledby="conversation-heading"] > ol > li',
      (items) => items.length,
    )
    expect(questions === 1, `${questions} exchanges on the page`)
    return 'one request, one exchange, and it ended (answer, passages or error)'
  })

  await step('9. no unexpected script errors', async () => {
    expect(unexpected.length === 0, unexpected.join(' | '))
  })
} finally {
  await browser.close()
}

const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length} of ${results.length} steps passed`)
process.exit(failed.length ? 1 : 0)
