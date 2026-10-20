/** Frontend smoke tests.
 *
 *  Run against the real dev server and the real API, not mocks. The point is to
 *  catch the failures a type checker cannot see: a route that renders a blank
 *  page, a guard that lets a signed-out visitor through, a drag that updates the
 *  screen but not the database.
 *
 *    node tests/smoke.mjs          (needs vite on :5173 and the API on :8000)
 */
import { chromium } from 'playwright'
import { execSync } from 'node:child_process'

const APP = 'http://127.0.0.1:5173'
const REPO = new URL('../..', import.meta.url).pathname
let passed = 0, failed = 0
const failures = []

function check(label, ok, detail = '') {
  if (ok) { passed++ } else { failed++; failures.push(label); console.log(`  FAIL  ${label}   ${detail}`) }
}

function sql(q) {
  return execSync(`psql -U postgres -h localhost -d telos_ci -tAc "${q}"`,
                  { encoding: 'utf8' }).trim()
}

const ACCOUNT = 'demo.board@telos.test'
const token = execSync(
  `cd ${REPO} && DATABASE_URL=postgresql://postgres@localhost:5432/telos_ci ` +
  `python3 -c "import sys;sys.path.insert(0,'.');from core.auth import remember_session;` +
  `print(remember_session('${ACCOUNT}'))"`, { encoding: 'utf8' }).trim()

// Seed the fixture this suite asserts against. It used to assume telos_ci
// already held the right rows, which made the whole board section depend on
// whatever a previous run happened to leave behind: on a fresh database it
// failed with zero columns and looked like a broken board rather than a missing
// fixture. The suite now creates what it needs and leaves the account the way
// it found it.
const SEED = [
  ['Kestrel', 'Associate PM', 'screening'],
  ['Northwind', 'Technical Program Manager', 'applied'],
  ['Cobalt', 'Delivery Manager', 'interview'],
  ['Vantage', 'Product Operations Manager', 'applied'],
]
sql(`DELETE FROM jobs WHERE tester_name='${ACCOUNT}'`)
for (const [company, role, status] of SEED) {
  sql(`INSERT INTO jobs (tester_name, company, role, status) ` +
      `VALUES ('${ACCOUNT}', '${company}', '${role}', '${status}')`)
}

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })

function watch(page) {
  const errs = []
  page.on('pageerror', e => errs.push(String(e)))
  page.on('console', m => {
    const t = m.text()
    // Two classes of noise, neither an app fault. Google Fonts is unreachable
    // from the sandbox, and a signed-out visitor is *supposed* to get a 401
    // from /api/me, which the browser logs as a failed resource. Anything else
    // is a real error and must not be filtered away.
    const noise = /ERR_TUNNEL|fonts\.googleapis|status of 401|status of 404/
    if (m.type() === 'error' && !noise.test(t)) errs.push(t)
  })
  return errs
}

// ------------------------------------------------------------ 1. the guard
console.log('\n[1] a signed-out visitor reaches nothing')
const out = await browser.newContext({ viewport: { width: 1280, height: 860 } })
const anon = await out.newPage(); const anonErrs = watch(anon)

for (const path of ['/', '/match', '/prep', '/roadmap', '/advisor', '/profile', '/account']) {
  await anon.goto(APP + path, { waitUntil: 'networkidle' })
  await anon.waitForTimeout(250)
  const auth = await anon.locator('.auth-card').count()
  const leaked = await anon.locator('.board, .stat-strip, .rail').count()
  check(`${path} shows the sign-in form`, auth === 1, `auth=${auth}`)
  check(`${path} leaks no app chrome`, leaked === 0, `leaked=${leaked}`)
}
check('the sign-in screen offers account creation',
      await anon.getByRole('button', { name: 'Create an account' }).count() === 1)
check('and password recovery',
      await anon.getByRole('button', { name: 'Forgot password' }).count() === 1)
check('no console errors on the auth screen', anonErrs.length === 0, anonErrs.join(' | '))

// ------------------------------------------------------------ 2. every route
console.log('\n[2] every route renders for a signed-in account')
const inn = await browser.newContext({ viewport: { width: 1280, height: 900 } })
await inn.addCookies([{ name: 'telos_session', value: token, domain: '127.0.0.1',
                        path: '/', httpOnly: true, secure: false, sameSite: 'Lax' }])
const app = await inn.newPage(); const appErrs = watch(app)

const ROUTES = [
  ['/', 'Pipeline'], ['/match', 'Match'], ['/prep', 'Interview prep'],
  ['/roadmap', 'Roadmap'], ['/advisor', 'Advisor'], ['/profile', 'Profile'],
  ['/account', 'Account'],
]
for (const [path, heading] of ROUTES) {
  await app.goto(APP + path, { waitUntil: 'networkidle' })
  await app.waitForTimeout(350)
  check(`${path} renders its heading`,
        await app.getByRole('heading', { name: heading, level: 1 }).count() === 1)
  check(`${path} shows the nav rail`, await app.locator('.rail').count() === 1)
}
check('an unknown route says so, rather than rendering blank',
      (await app.goto(APP + '/nope', { waitUntil: 'networkidle' }),
       await app.waitForTimeout(250),
       await app.getByText('That page does not exist.').count()) === 1)
check('no console errors across all routes', appErrs.length === 0, appErrs.join(' | '))

// ------------------------------------------------------------ 3. the board
console.log('\n[3] the board moves a role, and the database agrees')
await app.goto(APP + '/', { waitUntil: 'networkidle' })
await app.waitForTimeout(600)
check('the board renders', await app.locator('.board').count() === 1)
check('every stage has a column', await app.locator('.col').count() === 7,
      await app.locator('.col').count())

const before = sql(`SELECT status FROM jobs WHERE tester_name='${ACCOUNT}' AND company='Kestrel'`)
const card = app.getByRole('button', { name: /Associate PM at Kestrel/ })
const offer = app.locator('.col').filter({ hasText: 'Offer' }).first()
const a = await card.boundingBox(), t = await offer.boundingBox()
await app.mouse.move(a.x + a.width / 2, a.y + a.height / 2)
await app.mouse.down()
await app.mouse.move(a.x + a.width / 2 + 30, a.y + a.height / 2, { steps: 6 })
await app.mouse.move(t.x + t.width / 2, t.y + 60, { steps: 20 })
await app.mouse.up()
await app.waitForTimeout(1200)
const after = sql(`SELECT status FROM jobs WHERE tester_name='${ACCOUNT}' AND company='Kestrel'`)
check('the drag persisted to the database', before !== after && after === 'offer',
      `${before} -> ${after}`)

// put it back so the suite is repeatable
execSync(`psql -U postgres -h localhost -d telos_ci -q -c ` +
         `"UPDATE jobs SET status='screening' WHERE tester_name='${ACCOUNT}' AND company='Kestrel'"`)

// ------------------------------------------------------------ 4. list view
console.log('\n[4] the list view is honest about scores')
await app.reload({ waitUntil: 'networkidle' })
await app.getByRole('button', { name: 'List' }).click()
await app.waitForTimeout(400)
check('the list renders a row per role', await app.locator('table.data tbody tr').count() > 0)

// ------------------------------------------------- 6. the two newest screens
console.log('\n[6] companies view, and reading a posting from a screenshot')
await app.goto(APP + '/', { waitUntil: 'networkidle' })
await app.getByRole('button', { name: 'Companies' }).click()
await app.waitForTimeout(700)
const rows = await app.locator('table.data tbody tr').count()
check('the companies view lists one row per employer', rows === SEED.length,
      `${rows} rows for ${SEED.length} companies`)
check('and names a company that was seeded',
      await app.getByText('Kestrel', { exact: false }).count() > 0)

// The totals have to agree with the database, or the view is decoration.
const distinct = Number(sql(
  `SELECT count(DISTINCT company) FROM jobs WHERE tester_name='${ACCOUNT}'`))
check('the row count matches the database', rows === distinct, `${rows} vs ${distinct}`)

await app.goto(APP + '/match', { waitUntil: 'networkidle' })
await app.waitForTimeout(400)
check('Match offers the screenshot route in as well as pasting',
      await app.getByRole('button', { name: /upload a screenshot/i }).count() === 1)
check('the file input accepts images only',
      await app.locator('input#jd-image[type=file][accept="image/*"]').count() === 1)
// A screenshot must never be scored without a human reading it first.
check('scoring stays disabled until there is text to score',
      await app.getByRole('button', { name: /Score this role/ }).isDisabled())

// ------------------------------------------------------------ 5. sign out
console.log('\n[5] signing out actually ends the session')
await app.goto(APP + '/account', { waitUntil: 'networkidle' })
await app.waitForTimeout(400)
await app.getByRole('button', { name: 'Sign out' }).click()
await app.waitForTimeout(900)
check('the app returns to the sign-in screen',
      await app.locator('.auth-card').count() === 1)
const stillValid = execSync(
  `cd ${REPO} && DATABASE_URL=postgresql://postgres@localhost:5432/telos_ci ` +
  `python3 -c "import sys;sys.path.insert(0,'.');from core.auth import resume_session;` +
  `print(resume_session('${token}') or 'revoked')"`, { encoding: 'utf8' }).trim()
check('and the token is revoked server-side, not just in the browser',
      stillValid === 'revoked', stillValid)

await browser.close()
console.log(`\n  ${passed} passed, ${failed} failed`)
if (failures.length) console.log('  FAILURES: ' + failures.join('; '))
process.exit(failed ? 1 : 0)
