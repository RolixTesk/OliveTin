<template>
  <Section title="服务监控">
    <template #toolbar>
      <button
        type="button"
        :disabled="loading"
        @click="refresh"
      >
        刷新状态
      </button>
    </template>
    <p role="status">
      每 10 秒刷新 · 最近成功采集：{{ collectedAt || '等待采集' }}
    </p>
    <p
      v-if="error"
      role="alert"
    >
      {{ error }}
    </p>
    <div class="service-grid">
      <article
        v-for="service in services"
        :key="service.id"
        class="service-card"
      >
        <h2>{{ service.name }}</h2>
        <dl>
          <dt>运行</dt><dd>{{ service.state }}</dd>
          <dt>自启动</dt><dd>{{ service.enabled }}</dd>
          <dt>健康</dt><dd>{{ service.health || '未配置健康检查' }}</dd>
          <template
            v-for="(value, key) in service.details"
            :key="key"
          >
            <dt>{{ key }}</dt><dd>{{ value }}</dd>
          </template>
        </dl>
        <p v-if="service.note">
          {{ service.note }}
        </p>
        <a
          v-if="service.url"
          :href="service.url"
          target="_blank"
          rel="noopener noreferrer"
        >打开原管理页</a>
        <div class="service-actions">
          <ActionButton
            v-for="action in actionsFor(service)"
            :key="action.bindingId"
            :action-data="action"
          />
          <button
            type="button"
            @click="openLogs(service.id)"
          >
            业务日志
          </button>
        </div>
      </article>
    </div>
  </Section>
  <Section
    v-if="selectedService"
    :title="`业务日志 · ${selectedService}`"
  >
    <template #toolbar>
      <button
        type="button"
        :disabled="logsLoading"
        @click="openLogs(selectedService)"
      >
        刷新日志
      </button>
      <button
        type="button"
        @click="selectedService = ''"
      >
        关闭
      </button>
    </template>
    <p>最近最多 200 行；systemd 日志限最近 24 小时。常见敏感字段已过滤，动作执行记录在“Logs”页面。</p>
    <p
      v-if="logsError"
      role="alert"
    >
      {{ logsError }}
    </p>
    <pre class="business-log">{{ logs }}</pre>
  </Section>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
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
const abort = new AbortController()
let timer
let logRequest = 0

async function read (path) {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store', signal: abort.signal })
  if (!response.ok) throw new Error(response.status === 403 ? '请使用有管理权限的账号登录。' : '无法读取服务数据，请检查采集或网络状态。')
  return response
}

async function refresh () {
  if (loading.value || document.hidden) return
  loading.value = true
  try {
    const response = await read('/service-monitor/status')
    const result = await response.json()
    services.value = result.data?.services || []
    error.value = result.error || ''
    collectedAt.value = result.collectedAt?.startsWith('0001') ? '' : new Date(result.collectedAt).toLocaleString()
    await loadActions()
  } catch (err) {
    if (err.name !== 'AbortError') error.value = `${err.message} 已显示的数据可能过期。`
  } finally {
    loading.value = false
  }
}

async function loadActions () {
  const ids = services.value.flatMap(service => service.actions || []).filter(id => !actions.value[id])
  await Promise.all(ids.map(async id => {
    const response = await window.client.getActionBinding({ bindingId: id })
    if (response.action) actions.value[id] = response.action
  }))
}

function actionsFor (service) {
  return (service.actions || []).map(id => actions.value[id]).filter(Boolean)
}

async function openLogs (id) {
  const request = ++logRequest
  selectedService.value = id
  logs.value = ''
  logsError.value = ''
  logsLoading.value = true
  try {
    const response = await read(`/service-monitor/logs/${encodeURIComponent(id)}`)
    const output = await response.text()
    if (request === logRequest) logs.value = output
  } catch (err) {
    if (request === logRequest && err.name !== 'AbortError') logsError.value = err.message
  } finally {
    if (request === logRequest) logsLoading.value = false
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 10000)
})
onUnmounted(() => {
  clearInterval(timer)
  abort.abort()
})
</script>

<style scoped>
.service-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
.service-card { padding: 1rem; border: 1px solid var(--border-color, #888); border-radius: 0.5rem; }
.service-card dl { display: grid; grid-template-columns: auto 1fr; gap: 0.25rem 1rem; }
.service-card dd { margin: 0; overflow-wrap: anywhere; }
.service-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; }
.business-log { max-height: 65vh; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
