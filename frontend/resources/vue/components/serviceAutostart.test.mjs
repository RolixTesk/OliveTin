import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const source = readFileSync(new URL('../views/ServicesView.vue', import.meta.url), 'utf8')
function functions (names, globals = {}) {
  const code = names.map(name => {
    const match = source.match(new RegExp(`function ${name} \\([^]*?\\n(?=function |async function )`))
    assert.ok(match, `missing ${name}`)
    return match[0]
  }).join('\n')
  const context = vm.createContext(globals)
  vm.runInContext(code, context)
  return context
}

test('boot policies have distinct labels, including unknown and masked', () => {
  const { bootLabel } = functions(['bootLabel'])
  for (const [policy, label] of [['enabled', '开机启动'], ['always', '开机启动 · 自动恢复'], ['no', '未启用'], ['disabled', '未启用'], ['unless-stopped', '自动恢复 · 主动停止除外'], ['unknown', '未知'], ['masked', '已屏蔽']]) assert.equal(bootLabel(policy), label)
})
test('compound autostart action names retain their intended labels', () => {
  const { actionTitle } = functions(['actionTitle'])
  assert.equal(actionTitle('stalwart-enable-autostart', 'fallback'), '开启自启动')
  assert.equal(actionTitle('astrbot-disable-autostart', 'fallback'), '关闭自启动')
  assert.equal(actionTitle('astrbot-start', 'fallback'), '启动')
})
test('all controls for a service are disabled while any one is queued or running', () => {
  const buttonResults = { one: { bindingId: 'stalwart-enable-autostart', executionFinished: false } }
  const { serviceBusy } = functions(['serviceBusy'], { buttonResults })
  const service = { actions: ['stalwart-start', 'stalwart-enable-autostart', 'stalwart-disable-autostart'] }
  assert.equal(serviceBusy(service), true)
  assert.equal(serviceBusy({ actions: ['astrbot-start'] }), false)
  buttonResults.one.executionFinished = true
  buttonResults.one.exitCode = 1
  assert.equal(serviceBusy(service), false)
})

test('a failed autostart already finished when returning from logs remains visible', async () => {
  const { reactive, ref, watch, nextTick } = await import('vue')
  const buttonResults = reactive({ first: { bindingId: 'stalwart-enable-autostart', executionTrackingId: 'one', executionFinished: true, exitCode: 1, datetimeFinished: '2026-10-28T11:00:20Z' } })
  const policyError = ref('')
  const code = source.slice(source.indexOf('watch(() => Object.values(buttonResults)'), source.indexOf('onMounted(() => {'))
  const stops = []
  vm.runInNewContext(code, { buttonResults, policyError, watch: (...args) => stops.push(watch(...args)), refresh: () => {} })
  await nextTick()
  assert.match(policyError.value, /失败/)
  stops.forEach(stop => stop())
})

test('latest completion wins when operations finish out of their start order', async () => {
  const { reactive, ref, watch, nextTick } = await import('vue')
  const buttonResults = reactive({ slow: { bindingId: 'stalwart-enable-autostart', executionTrackingId: 'one', executionFinished: false }, fast: { bindingId: 'astrbot-enable-autostart', executionTrackingId: 'two', executionFinished: true, exitCode: 0, datetimeFinished: '2026-10-28T11:00:10Z' } })
  const policyError = ref('')
  const code = source.slice(source.indexOf('watch(() => Object.values(buttonResults)'), source.indexOf('onMounted(() => {'))
  const stops = []
  vm.runInNewContext(code, { buttonResults, policyError, watch: (...args) => stops.push(watch(...args)), refresh: () => {} })
  buttonResults.slow = { ...buttonResults.slow, executionFinished: true, exitCode: 1, datetimeFinished: '2026-10-28T11:00:20Z' }
  await nextTick()
  assert.match(policyError.value, /失败/)
  stops.forEach(stop => stop())
})
