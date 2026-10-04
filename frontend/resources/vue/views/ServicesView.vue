<template>
  <div class="services-view">
    <div class="services-heading">
      <div><span class="eyebrow">ROLIXTESK · SERVICES</span><h1>你的服务，一目了然。</h1><p>机器人、同步、邮件与网络，都在这里。</p></div>
      <button
        type="button"
        :disabled="loading"
        @click="refresh"
      >
        {{ loading ? '更新中…' : '刷新状态' }}
      </button>
    </div>
    <div
      class="services-overview"
      role="status"
    >
      <span><strong>{{ services.length }}</strong> 项服务</span><span><strong>{{ runningCount }}</strong> 项运行中</span>
      <span class="collection-time">每 10 秒更新 · {{ collectedAt || '等待采集' }}</span>
    </div>
    <p
      v-if="error"
      class="service-alert"
      role="alert"
    >
      {{ error }}
    </p>
    <p
      v-if="!services.length && !error"
      class="service-empty"
    >
      正在读取服务状态…
    </p>
    <div
      v-for="group in groupedServices"
      :key="group.name"
      class="service-group"
    >
      <h2 class="group-title">
        {{ group.name }} <span>{{ group.items.length }}</span>
      </h2>
      <div class="service-grid">
        <div
          v-for="service in group.items"
          :key="service.id"
          class="service-tile"
        >
          <article class="service-card">
            <div class="service-card-heading">
              <div class="service-icon">
                <img
                  v-if="icons[service.id]"
                  :src="icons[service.id]"
                  alt=""
                ><span v-else>{{ service.id.slice(0, 2).toUpperCase() }}</span>
              </div>
              <div class="service-title">
                <h2>{{ service.name }}</h2><p>{{ descriptions[service.id] }}</p>
              </div>
              <span
                class="state-badge"
                :data-state="service.state"
              >{{ stateLabel(service.state) }}</span>
            </div>
            <dl>
              <dt>自启动</dt><dd>{{ bootLabel(service.enabled) }}</dd><dt>健康检查</dt><dd>{{ healthLabel(service.health) }}</dd>
              <template
                v-for="(value, key) in service.details"
                :key="key"
              >
                <dt>{{ key }}</dt><dd>{{ key === 'QQ 登录' ? loginLabel(value) : value }}</dd>
              </template>
            </dl>
            <p
              v-if="service.note"
              class="service-note"
            >
              {{ service.note }}
            </p>
            <div class="service-utilities">
              <button
                type="button"
                @click="openLogs(service.id)"
              >
                业务日志
              </button>
              <button
                v-if="service.id === 'napcat'"
                type="button"
                @click="openLogin"
              >
                QQ 登录
              </button>
              <button
                v-if="service.id === 'napcat'"
                type="button"
                :disabled="tokenLoading"
                @click="copyToken"
              >
                {{ tokenLoading ? '读取中…' : '复制 WebUI token' }}
              </button>
              <a
                v-if="service.url"
                :href="service.url"
                target="_blank"
                rel="noopener noreferrer"
              >原管理页 ↗</a>
            </div>
            <p
              v-if="service.id === 'napcat' && tokenFeedback"
              class="service-note token-feedback"
              role="status"
            >
              {{ tokenFeedback }}
            </p>
            <div
              v-if="service.actions?.length"
              class="service-actions"
            >
              <ActionButton
                v-for="action in actionsFor(service)"
                :key="action.bindingId"
                :action-data="action"
              />
            </div>
          </article>
          <div
            v-if="service.id === 'napcat'"
            id="napcat-panels"
          >
            <Section
              v-if="showLogin"
              title="NapCat · QQ 登录"
              classes="qq-login-section"
            >
              <template #toolbar>
                <button
                  type="button"
                  :disabled="loginLoading"
                  @click="refreshLogin"
                >
                  重新读取
                </button><button
                  type="button"
                  @click="closeLogin"
                >
                  关闭
                </button>
              </template>
              <p
                v-if="loginError"
                role="alert"
              >
                {{ loginError }}
              </p>
              <div
                v-else
                class="qq-login-content"
              >
                <div
                  v-if="loginData?.qrImage"
                  class="qq-qr"
                >
                  <img
                    :src="loginData.qrImage"
                    alt="QQ 登录二维码"
                  ><span>请使用手机 QQ 扫码授权</span>
                </div>
                <div>
                  <h3>{{ loginLabel(loginData?.status) }}</h3><p>{{ loginData?.message || '正在读取本次启动的登录事件…' }}</p>
                  <p
                    v-if="loginData?.eventAt"
                    class="service-note"
                  >
                    事件时间：{{ formatTime(loginData.eventAt) }}
                  </p>
                  <p
                    v-if="loginData?.qrExpiresAt"
                    class="service-note"
                  >
                    二维码展示截止：{{ formatTime(loginData.qrExpiresAt) }}
                  </p>
                  <p
                    v-if="loginData?.checkedAt"
                    class="service-note"
                  >
                    最近检测：{{ formatTime(loginData.checkedAt) }}
                  </p>
                  <p
                    v-if="loginData?.containerStartedAt"
                    class="service-note"
                  >
                    本次容器启动：{{ formatTime(loginData.containerStartedAt) }}
                  </p>
                  <p class="service-note">
                    每 10 秒检测。QQ 登录事件不等同于 OneBot 连接或 AstrBot 消息处理状态。
                  </p>
                </div>
              </div>
            </Section>
          </div>
        </div>
      </div>
    </div>
    <Teleport
      to="#napcat-panels"
      :disabled="selectedService !== 'napcat'"
    >
      <Section
        v-if="selectedService"
        :title="`业务日志 · ${selectedServiceName}`"
        classes="business-log-section"
      >
        <template #toolbar>
          <button
            type="button"
            :disabled="logsLoading"
            @click="openLogs(selectedService)"
          >
            刷新日志
          </button><button
            type="button"
            @click="selectedService = ''"
          >
            关闭
          </button>
        </template>
        <p class="service-note">
          最近最多 200 行；systemd 日志限本次开机的最近 24 小时。动作执行记录在“Logs”页面。
        </p>
        <p
          v-if="logsError"
          role="alert"
        >
          {{ logsError }}
        </p><p
          v-else-if="logsLoading"
          role="status"
        >
          正在读取业务日志…
        </p><p
          v-else-if="!logs.trim()"
          role="status"
        >
          当前范围内没有日志。
        </p>
        <pre
          v-else
          class="business-log"
        >{{ logs }}</pre>
      </Section>
    </Teleport>
  </div>
</template>
<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import Section from 'picocrank/vue/components/Section.vue'
import ActionButton from '../ActionButton.vue'
const services = ref([])
const actions = ref({})
const error = ref('')
const loading = ref(false)
const collectedAt = ref('')
const selectedService = ref('')
const logs = ref('')
const logsError = ref('')
const logsLoading = ref(false)
const showLogin = ref(false)
const loginData = ref(null)
const loginError = ref('')
const loginLoading = ref(false)
const tokenLoading = ref(false)
const tokenFeedback = ref('')
const abort = new AbortController()
let timer
let qrExpiryTimer
let logRequest = 0
let loginRequest = 0
const icons = { astrbot: '/personal/astrbot.svg', napcat: '/personal/napcat-logo.png', couchdb: '/personal/couchdb-logo.png', clash: '/personal/clash.ico' }
const descriptions = { astrbot: 'AI 对话与消息处理', napcat: 'QQ 登录与 OneBot 接入', couchdb: 'Obsidian 数据同步', stalwart: '邮件接收与投递', roundcube: '浏览器中的邮件入口', hoyopanel: '个人业务与任务面板', clash: 'Mihomo 代理服务', nginx: '站点与 HTTPS 入口', docker: '容器运行环境', wireguard: '私有管理隧道' }
const groups = [{ name: '机器人', ids: ['astrbot', 'napcat'] }, { name: '同步与邮件', ids: ['couchdb', 'stalwart', 'roundcube'] }, { name: '站点与网络', ids: ['hoyopanel', 'clash', 'nginx', 'docker', 'wireguard'] }]
const groupedServices = computed(() => groups.map(group => ({ name: group.name, items: services.value.filter(service => group.ids.includes(service.id)) })).filter(group => group.items.length))
const runningCount = computed(() => services.value.filter(service => ['active', 'running'].includes(service.state)).length)
const selectedServiceName = computed(() => services.value.find(service => service.id === selectedService.value)?.name || selectedService.value)
function stateLabel (state) { return ({ active: '运行中', running: '运行中', stopped: '已停止', inactive: '已停止', exited: '已退出', failed: '故障', unknown: '未知' })[state] || state }
function bootLabel (value) { return ({ enabled: '开机启动', 'unless-stopped': '自动恢复 · 主动停止除外', disabled: '未启用', unknown: '未知' })[value] || value }
function healthLabel (value) { return ({ healthy: '健康', unhealthy: '异常', unconfigured: '未配置', success: '最近运行正常', 'collection-error': '采集失败' })[value] || value || '未配置' }
function loginLabel (value) { return ({ unknown: '暂时无法确认', 'login-required': '等待扫码', 'logged-in': '已登录', scanning: '正在确认登录', expired: '二维码已失效', failed: '登录失败', stopped: 'NapCat 未运行' })[value] || '正在检测' }
function formatTime (value) { return new Date(value).toLocaleString() }
async function read (path) {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', signal: abort.signal })
  if (!response.ok) throw new Error(response.status === 403 ? '请使用有管理权限的账号登录。' : '无法读取服务数据，请检查采集或网络状态。')
  return response
}
async function refresh () {
  if (loading.value || document.hidden) return
  loading.value = true
  try {
    const result = await (await read('/service-monitor/status')).json()
    services.value = result.data?.services || []
    error.value = result.error || ''
    collectedAt.value = result.collectedAt?.startsWith('0001') ? '' : formatTime(result.collectedAt)
    await loadActions()
  } catch (err) {
    if (err.name !== 'AbortError') error.value = `${err.message} 已显示的数据可能过期。`
  } finally { loading.value = false }
}
async function loadActions () {
  const ids = services.value.flatMap(service => service.actions || []).filter(id => !actions.value[id])
  await Promise.all(ids.map(async id => {
    const response = await window.client.getActionBinding({ bindingId: id }); if (response.action) {
      response.action.title = ({ start: '启动', stop: '停止', restart: '重启', check: '配置检查', reload: '重载配置' })[id.split('-').pop()] || response.action.title
      actions.value[id] = response.action
    }
  }))
}
function actionsFor (service) { return (service.actions || []).map(id => actions.value[id]).filter(Boolean) }
async function openLogs (id) {
  const request = ++logRequest
  selectedService.value = id
  nextTick(() => document.querySelector('.business-log-section')?.scrollIntoView({ block: 'start' }))
  logs.value = ''; logsError.value = ''; logsLoading.value = true
  try {
    const output = await (await read(`/service-monitor/logs/${encodeURIComponent(id)}`)).text()
    if (request === logRequest) logs.value = output
  } catch (err) {
    if (request === logRequest && err.name !== 'AbortError') logsError.value = err.message
  } finally { if (request === logRequest) logsLoading.value = false }
}
async function copyToken () {
  if (tokenLoading.value) return
  tokenLoading.value = true; tokenFeedback.value = ''
  try {
    const data = await (await read('/service-monitor/napcat-token')).json()
    if (!data.token) throw new Error(data.message || '本次启动的日志中未找到 WebUI token。')
    try { await navigator.clipboard.writeText(data.token) } catch { throw new Error('无法写入剪切板，请允许浏览器的剪切板权限后重试。') }
    tokenFeedback.value = 'WebUI token 已复制到剪切板。'
  } catch (err) {
    if (err.name !== 'AbortError') tokenFeedback.value = err.message
  } finally { tokenLoading.value = false }
}
function closeLogin () { clearTimeout(qrExpiryTimer); showLogin.value = false; loginData.value = null; loginRequest++; loginLoading.value = false }
function openLogin () {
  showLogin.value = true
  nextTick(() => document.querySelector('.qq-login-section')?.scrollIntoView({ block: 'start' }))
  refreshLogin()
}
async function refreshLogin () {
  if (loginLoading.value || !showLogin.value || document.hidden) return
  const request = ++loginRequest
  loginLoading.value = true
  try {
    const data = await (await read('/service-monitor/napcat-login')).json()
    if (request !== loginRequest) return
    loginData.value = data; loginError.value = ''
    clearTimeout(qrExpiryTimer)
    if (data.qrImage && data.qrExpiresAt) {
      qrExpiryTimer = setTimeout(() => {
        loginData.value = { ...loginData.value, qrImage: '', status: 'expired', message: '二维码已超出有效窗口，正在检测更新。' }
      }, Math.max(0, Date.parse(data.qrExpiresAt) - Date.now()))
    }
  } catch (err) {
    if (request === loginRequest && err.name !== 'AbortError') { loginData.value = null; loginError.value = err.message }
  } finally { if (request === loginRequest) loginLoading.value = false }
}
onMounted(() => {
  refresh()
  timer = setInterval(() => {
    refresh()
    if (loginData.value?.qrExpiresAt && Date.now() >= Date.parse(loginData.value.qrExpiresAt)) loginData.value = { ...loginData.value, qrImage: '', status: 'expired', message: '二维码已超出有效窗口，正在检测更新。' }
    refreshLogin()
  }, 10000)
})
onUnmounted(() => { clearInterval(timer); clearTimeout(qrExpiryTimer); abort.abort() })
</script>
<style scoped>
.services-heading { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin: .5rem 0 1.5rem; }
.eyebrow { letter-spacing: .16em; font-size: .68rem; color: var(--site-accent); font-weight: 700; }
.services-heading h1 { font-size: clamp(1.6rem, 3vw, 2.15rem); letter-spacing: -.045em; margin: .45rem 0; }
.services-heading p, .service-title p { color: var(--site-muted); margin: 0; font-size: .9rem; }
.services-heading button { white-space: nowrap; background: var(--site-surface); }
.services-overview { display: flex; flex-wrap: wrap; gap: 1.2rem; padding: 1rem 1.3rem; border: 1px solid var(--site-line); border-radius: 16px; background: var(--site-surface); backdrop-filter: blur(12px); font-size: .85rem; }
.services-overview strong { font-size: 1.25rem; margin-right: .2rem; }
.collection-time { margin-left: auto; color: var(--site-muted); align-self: center; }
.service-group { margin-top: 1.8rem; }
.group-title { font-size: 1rem; font-weight: 600; margin-bottom: .8rem; }
.group-title span { color: var(--site-muted); font-size: .75rem; margin-left: .3rem; }
.service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); gap: 1rem; align-items: start; }
.service-tile { min-width: 0; }
.service-card { display: flex; flex-direction: column; padding: 1.2rem; min-width: 0; border: 1px solid var(--site-line); border-radius: 16px; background: var(--site-surface); backdrop-filter: blur(12px); box-shadow: 0 8px 32px rgb(31 38 135 / 12%); }
.service-card-heading { display: flex; align-items: center; gap: .7rem; margin-bottom: 1.1rem; }
.service-icon { width: 44px; height: 44px; flex: 0 0 auto; display: grid; place-items: center; background: rgb(37 99 235 / 12%); color: var(--site-accent); border-radius: 12px; font-size: .9rem; font-weight: 700; }
.service-icon img { width: 27px; height: 27px; object-fit: contain; }
.service-title { min-width: 0; }
.service-title h2 { font-size: .95rem; margin: 0 0 .25rem; }
.service-title p { font-size: .72rem; }
.state-badge { margin-left: auto; flex-shrink: 0; border-radius: 999px; padding: .3rem .5rem; font-size: .68rem; background: var(--site-card); }
.state-badge[data-state="active"], .state-badge[data-state="running"] { color: #0f6b45; background: #d4f3e3; }
.state-badge[data-state="failed"] { color: #a62438; background: #ffe0e5; }
.service-card dl { display: grid; grid-template-columns: auto 1fr; gap: .55rem .8rem; font-size: .78rem; margin: 0; }
.service-card dt { color: var(--site-muted); }
.service-card dt, .service-card dd { padding: 0; border: 0; text-align: left; }
.service-card dd { margin: 0; overflow-wrap: anywhere; }
.service-note { color: var(--site-muted); font-size: .75rem; line-height: 1.6; }
.service-utilities { display: flex; flex-wrap: wrap; align-items: center; gap: .45rem; margin-top: auto; padding-top: 1rem; }
.service-utilities button, .service-utilities a { font-size: .75rem; }
.service-utilities a { margin-left: auto; }
.service-actions { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .75rem; padding-top: .75rem; border-top: 1px solid var(--site-line); }
.service-actions :deep(button) { font-size: .68rem; padding: .4rem .55rem; min-height: 30px; }
.service-actions :deep(.icon), .service-actions :deep(.navigate-on-start-container) { display: none; }
.services-view .service-actions :deep(.action-button button) { background: var(--site-card); color: var(--text-color); border: 1px solid var(--site-line); box-shadow: none; }
.service-alert { padding: 1rem; border-radius: 12px; background: #ffe8ce; color: #754406; }
.service-empty { padding: 2rem; text-align: center; }
.business-log { max-height: 60vh; overflow: auto; border-radius: 12px; padding: 1rem; background: var(--site-solid); color: var(--text-color); white-space: pre-wrap; overflow-wrap: anywhere; font-size: .75rem; }
.qq-login-content { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; }
.qq-qr { display: flex; flex-direction: column; gap: .7rem; text-align: center; font-size: .75rem; }
.qq-qr img { width: 210px; height: 210px; background: white; padding: 12px; border-radius: 12px; image-rendering: pixelated; box-sizing: content-box; }
:deep(.qq-login-section), :deep(.business-log-section) { margin-top: 1.6rem; }
@media (max-width: 640px) { .services-heading { flex-wrap: wrap; } .collection-time { margin-left: 0; width: 100%; } .service-card { padding: 1rem; } .service-actions :deep(button) { min-height: 44px; } .qq-login-content { flex-direction: column; align-items: flex-start; } }
</style>
