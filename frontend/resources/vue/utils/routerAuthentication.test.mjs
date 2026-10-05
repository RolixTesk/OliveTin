import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { runInNewContext } from 'node:vm'

function loadRouter () {
  const guards = []
  let routes
  const window = {}
  const source = readFileSync(new URL('../router.js', import.meta.url), 'utf8')
    .replace(/^import .*$/gm, '')
    .replace('export default router', '')
  runInNewContext(source, {
    window,
    document: {},
    Dashboard: {},
    Wrench01Icon: {},
    LeftToRightListDashIcon: {},
    CellsIcon: {},
    DashboardSquare01Icon: {},
    createWebHistory: () => ({}),
    createRouter: options => {
      routes = options.routes
      return { beforeEach: guard => guards.push(guard) }
    }
  })
  return { window, services: routes.find(route => route.name === 'Services'), system: routes.find(route => route.name === 'System'), guard: guards.at(-1) }
}

test('services navigation follows Init identity through login and logout', () => {
  const { window, services, guard } = loadRouter()
  window.initResponse = { loginRequired: true, authenticatedUser: 'guest' }
  assert.equal(guard(services), '/login')
  assert.equal(guard({ name: 'Login', meta: {} }), undefined)
  window.initResponse = { loginRequired: false, authenticatedUser: 'admin' }
  assert.equal(guard(services), undefined)
  window.initResponse = { loginRequired: false, authenticatedUser: 'guest' }
  window.isAuthenticated = true
  assert.equal(guard(services), '/login')
  window.initResponse = undefined
  assert.equal(guard(services), '/login')
})


test('system history page follows the authenticated identity', () => {
  const { window, system, guard } = loadRouter()
  window.initResponse = { loginRequired: true, authenticatedUser: 'guest' }
  assert.equal(guard(system), '/login')
  window.initResponse = { loginRequired: false, authenticatedUser: 'admin' }
  assert.equal(guard(system), undefined)
  window.initResponse = { loginRequired: false, authenticatedUser: 'guest' }
  assert.equal(guard(system), '/login')
})
